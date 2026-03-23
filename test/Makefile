# Makefile
# See https://docs.cocotb.org/en/stable/quickstart.html for more info

# defaults
SIM ?= icarus
FST ?= -fst # Use more efficient FST format
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src
PROJECT_SOURCES = tt_um_elemental_harmony.v


ifneq ($(GATES),yes)

# --- THE FIX ---
# Point directly to the binary to bypass the broken shell wrapper
#VVP_REAL = /home/zerotoasic/asic_tools/oss-cad-suite/py3bin/vvp

#ifeq ($(SIM),icarus)
 #   override VVP := $(VVP_REAL)
  #  $(info --- VVP has been overriden to $(VVP_REAL) ---) 
#endif
# ---------------

# RTL simulation:
SIM_BUILD				= sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))
# Force the simulator to use the raw binary, bypassing the broken shell wrapper
#SIM_BINARY = /home/zerotoasic/asic_tools/oss-cad-suite/bin/
#VVP_BIN = /home/zerotoasic/asic_tools/oss-cad-suite/bin/.vvp

# Tell cocotb to use our specific vvp binary
#override VVP := $(VVP_BIN)

else

# Gate level simulation:
SIM_BUILD				= sim_build/gl
COMPILE_ARGS    += -DGL_TEST
COMPILE_ARGS    += -DFUNCTIONAL
COMPILE_ARGS    += -DSIM
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_io/verilog/sg13g2_io.v
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/sg13g2_stdcell.v

# this gets copied in by the GDS action workflow
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

endif

# Allow sharing configuration between design and testbench via `include`:
COMPILE_ARGS 		+= -I$(SRC_DIR)

# Include the testbench sources:
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb

# List test modules to run, separated by commas and without the .py suffix:
COCOTB_TEST_MODULES = test

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim
