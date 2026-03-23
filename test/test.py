import cocotb
import random
import os
import numpy as np
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

# --- GLOBAL SCOREBOARD CLASS ---
class HardwareScoreboard:
    def __init__(self, log):
        self.log = log
        # 4x4 board initialized to -1 (empty)
        self.board = np.full((4, 4), -1, dtype=int)
        
        # Mismatch Counters
        self.human_mismatches = 0
        self.design_mismatches = 0
        self.total_mismatches = 0

        # Pairwise LUT from the pattern table
        self.lut = np.array([
            [ 0,  1, -2, -2, -2,  2, -2,  2], # AB (0)
            [ 1,  0,  2, -2,  2, -2, -2,  2], # AG (1)
            [-2,  2,  0,  1, -2,  2,  2,  2], # WD (2)
            [-2, -2,  1,  0, -2,  2,  2,  2], # WR (3)
            [-2,  2, -2, -2,  0,  1, -2,  2], # FB (4)
            [ 2, -2,  2,  2,  1,  0, -2,  2], # FS (5)
            [-2, -2,  2,  2, -2, -2,  0,  1], # EG (6)
            [ 2,  2,  2,  2,  2,  2,  1,  0]  # EP (7)
        ])

    def get_score_and_update(self, pattern, position):
        """Calculates pairwise score against existing neighbors. 
        If neighbors == 0, returns +2 bonus."""
        row, col = divmod(position, 4)
        delta = 0
        neighbor_count = 0
        
        for dr, dc in [(-1, 0), (1, 0), (0, 1), (0, -1)]:
            nr, nc = row + dr, col + dc
            if 0 <= nr < 4 and 0 <= nc < 4:
                neighbor_pat = self.board[nr, nc]
                if neighbor_pat != -1:
                    delta += self.lut[pattern, neighbor_pat]
                    neighbor_count += 1
        
        # Apply +2 bonus for lonely cells (0 neighbors)
        if neighbor_count == 0:
            delta = 2
            
        self.board[row, col] = pattern
        return delta

    def check_score(self, actual, expected, player_type="Human"):
        """Validates score and increments specific mismatch counters."""
        if actual != expected:
            self.total_mismatches += 1
            if player_type == "Human":
                self.human_mismatches += 1
            else:
                self.design_mismatches += 1
            
            self.log.error(f"MISMATCH [{player_type}]: Expected {expected}, Got {actual}")
            return False
        return True

@cocotb.test()
async def test_harmony_final(dut):
    # --- 1. SEEDING & SETUP ---
    seed = int(os.environ.get('TESTSEED', 52))
    random.seed(seed)
    dut._log.info(f"SIMULATION START - Seed: {seed}")

    # Initialize Scoreboard with dut log for error reporting
    scoreboard = HardwareScoreboard(dut._log)

    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    # --- 2. HARDWARE RESET ---
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    total_h = 0
    total_d = 0
    
    # --- 3. MAIN GAME LOOP (8 ROUNDS) ---
    for r_idx in range(1, 9):
        await RisingEdge(dut.clk)
        dut._log.info(f"\n--- ROUND {r_idx} ---")
        
        # Initial guess (might collide)
        my_pos = random.randint(0, 15)
        my_pat = random.randint(1, 7)

        move_accepted = False
        while not move_accepted:
            # 1. Pulse Start with the current my_pos
            dut.ui_in.value = (1 << 7) | (my_pat << 4) | my_pos
            await RisingEdge(dut.clk)
            dut.ui_in.value = (my_pat << 4) | my_pos 
            
            # 2. Monitor for Success or Error sequence
            occ_msb = 0
            occ_lsb = 0
            
            while True:
                await RisingEdge(dut.clk)
                #curr_s = int(curr_s) #caused error so changed it

                curr_s = int(dut.user_project.uio_out.value[3:1])
	
                if curr_s == 2: # ST_HUMANPLAY
                    move_accepted = True
                    break # Exit monitor loop, move_accepted=True exits retry loop
                
                elif curr_s == 4: # ST_ERROR_1
                    # Sample fill count immediately after the edge
                    pass 
                
                elif curr_s == 5: # ST_ERROR_2
                    occ_msb = int(dut.uo_out.value)
                
                elif curr_s == 6: # ST_ERROR_3
                    occ_lsb = int(dut.uo_out.value)
                    
                    # --- THE IMMEDIATE RECOVERY ---
                    recovered_occ = (occ_msb << 8) | occ_lsb
                    available_slots = [i for i in range(16) if not ((recovered_occ >> i) & 1)]
                    
                    if not available_slots:
                        dut._log.error("Board Full!")
                        return # Kill test if no moves left
                    
                    # Update my_pos IMMEDIATELY while still in Error 3
                    dut._log.info(f"Collision! Move tried at Old colliding Pos: {my_pos}")
                    my_pos = random.choice(available_slots)
                    dut._log.info(f"Collision! Recovered OCC {bin(recovered_occ)}. Retrying Pos: {my_pos}")
                    
                    # 3. EXIT THE MONITOR LOOP IMMEDIATELY
                    # By breaking here, the code jumps back to 'dut.ui_in.value = (1 << 7)...'
                    # precisely as the FSM enters the IDLE state.
                    
                    break # Exit monitor loop to re-run the 'while not move_accepted' logic 
     
        dut._log.info(f"Human Move: Pos {my_pos}, Pat {my_pat}")

        # --- C. SAMPLE HUMAN SCORE ---
        while curr_s != 2:
            await RisingEdge(dut.clk)

        h_round_score = dut.uo_out.value.to_signed()
        expected_h = scoreboard.get_score_and_update(my_pat, my_pos)
        
        # Perform check and increment counters
        scoreboard.check_score(h_round_score, expected_h, "Human")
        
        total_h += h_round_score
        #dut.user_project.debug_score_h.value = h_round_score
        dut._log.info(f"Round {r_idx} HUMAN Score Recorded by RTL: {h_round_score} | Total: {total_h}")

        # --- D. SAMPLE DESIGN SCORE ---
        while curr_s != 3:
            await RisingEdge(dut.clk)

        d_round_score = 0
        design_pat = 0
        lfsr_pos = 0

        while True:
            if (dut.uio_out.value.to_unsigned() & 0x01):
                d_round_score = dut.uo_out.value.to_signed()
                design_pat = dut.user_project.dut_core.design_pat.value.to_unsigned()
                lfsr_pos   = dut.user_project.dut_core.lfsr_pos.value.to_unsigned()
            
            await RisingEdge(dut.clk)
            if curr_s != 3:
                break 

        # --- SCOREBOARD CALL (DESIGN) ---
        expected_d = scoreboard.get_score_and_update(design_pat, lfsr_pos)
        
        # Perform check and increment counters
        scoreboard.check_score(d_round_score, expected_d, "Design")

        total_d += d_round_score
        #dut.user_project.debug_score_d.value = d_round_score
        dut._log.info(f"Design Move: Pos {lfsr_pos}, Pat {design_pat}")
        dut._log.info(f"Round {r_idx} DESIGN Score Recorded by RTL: {d_round_score} | Total: {total_d}")

        # E. HANDSHAKE
        while curr_s not in [0, 7]:
            await RisingEdge(dut.clk)

    # --- 4. FINAL RESULTS & MISMATCH SUMMARY ---
    dut._log.info("\n" + "="*45)
    dut._log.info(f"FINAL SCORE - Human: {total_h} | Design: {total_d}")
    dut._log.info("-" * 45)
    dut._log.info(f"MISMATCH SUMMARY:")
    dut._log.info(f"  Human Mismatches:  {scoreboard.human_mismatches}")
    dut._log.info(f"  Design Mismatches: {scoreboard.design_mismatches}")
    dut._log.info(f"  Total Mismatches:  {scoreboard.total_mismatches}")
    dut._log.info("="*45 + "\n")

    # Crucial: Wait a few cycles before ending to flush the wave file
    await ClockCycles(dut.clk, 50)
        
    # Now finally fail the test if there were issues
    assert scoreboard.total_mismatches == 0, f"Test failed with {scoreboard.total_mismatches} mismatches!"

    await ClockCycles(dut.clk, 20)
