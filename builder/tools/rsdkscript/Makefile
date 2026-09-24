# Host (macOS/Linux) build of the RetroScript v2 compiler for the PS1 port.
ENGINE = ../../RSDKv2
CXX ?= clang++
CXXFLAGS = -std=c++17 -O1 -g -DRETRO_PS1_HOST_TOOL -I$(ENGINE) -Wno-everything
SRCS = main.cpp host_stubs.cpp $(ENGINE)/Script.cpp $(ENGINE)/Reader.cpp $(ENGINE)/String.cpp

rsdkscript: $(SRCS) $(wildcard $(ENGINE)/*.hpp)
	$(CXX) $(CXXFLAGS) -o $@ $(SRCS)

clean:
	rm -f rsdkscript
.PHONY: clean
