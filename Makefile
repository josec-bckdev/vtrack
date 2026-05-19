# VTrack Root Makefile — delegates to scripts/Makefile
# Usage: make <target> (from project root)

.PHONY: help

# Default target
.DEFAULT_GOAL := help

# Delegate all targets to scripts/Makefile
%:
	@$(MAKE) -f scripts/Makefile $@

help:
	@echo "VTrack Development Commands"
	@echo "Run from project root: make <target>"
	@echo ""
	@$(MAKE) -f scripts/Makefile help
