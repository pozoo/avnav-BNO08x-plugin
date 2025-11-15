# Configuration
GITHUB_REPO = https://github.com/pozoo/SparkFun_BNO08x_RaspberryPi_Library.git
BRANCH = raspi_spi_comm
BUILD_DIR = build
REPO_NAME = SparkFun_BNO08x_RaspberryPi_Library
DEST_DIR = BNO08x

.PHONY: all clean clone compile install

all: install

clone:
	@mkdir -p $(BUILD_DIR)
	@if [ ! -d "$(BUILD_DIR)/$(REPO_NAME)" ]; then \
		echo "Cloning $(GITHUB_REPO)..."; \
		git clone -b $(BRANCH) $(GITHUB_REPO) $(BUILD_DIR)/$(REPO_NAME); \
	else \
		echo "Repository already cloned in $(BUILD_DIR)/$(REPO_NAME)"; \
		cd $(BUILD_DIR)/$(REPO_NAME) && git checkout $(BRANCH) && git pull; \
	fi

compile: clone
	@echo "Building in $(BUILD_DIR)/$(REPO_NAME)..."
	$(MAKE) -C $(BUILD_DIR)/$(REPO_NAME)

install: compile
	@echo "Installing bno08x module to $(DEST_DIR)..."
	@cp $(BUILD_DIR)/$(REPO_NAME)/python/bno08x.cpython*.so $(DEST_DIR)/
	@echo "Installation complete."

clean:
	@echo "Cleaning build directory and installed files..."
	rm -rf $(BUILD_DIR)
	rm -f $(DEST_DIR)/bno08x.cpython*.so
