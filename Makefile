# Makefile to build deb and rpm packages to install mount.ibmshare on target Linux machines.

NAME := mount.ibmshare
APP_VERSION := 0.0.2
MAINTAINER := "Genctl Share"
DESCRIPTION := "IBM Mount Share helper"
LICENSE := "IBM"
DEB_ARCH := all
RPM_ARCH := noarch
RPM_RELEASE_NUM := 1


BUILD_DIR := $(NAME)-$(APP_VERSION)
MOUNT_SCRIPT := /sbin/$(NAME)

CONTROL := $(BUILD_DIR)/DEBIAN/control
POST_INSTALL := $(BUILD_DIR)/DEBIAN/postinst
REDHAT_SPEC := $(BUILD_DIR)/red-hat.spec
PYTHON_MERGE_SCRIPT := "$(PWD)/scripts/create_mount_ibmshare.py"
INSTALL_TAR_FILE := "$(NAME)-latest.tar.gz"
CHECKSUM_FILE := "$(INSTALL_TAR_FILE).sha256"

#MIN_PYTHON_VER := 3.8
#MIN_STRONGSWAN_VER := 5.8.2

MIN_PYTHON_VER := 3.4
MIN_STRONGSWAN_VER := 5.6


deb-build:
	rm -rf $(BUILD_DIR)

	python3 $(PYTHON_MERGE_SCRIPT) ./src $(BUILD_DIR)/$(MOUNT_SCRIPT)
	chmod 755 $(BUILD_DIR)/$(MOUNT_SCRIPT)

	mkdir -p $(BUILD_DIR)/DEBIAN

	echo "Package: $(BUILD_DIR)" > $(CONTROL)
	echo "Version: $(APP_VERSION)" >> $(CONTROL)
	echo "Maintainer: $(MAINTAINER)" >> $(CONTROL)
	echo "Architecture: $(DEB_ARCH)" >> $(CONTROL)
	echo "Description: $(DESCRIPTION)" >> $(CONTROL)
	#echo "Depends: python3(>= $(MIN_PYTHON_VER)), strongswan-swanctl(>= $(MIN_STRONGSWAN_VER)), charon-systemd(>= $(MIN_STRONGSWAN_VER)), nfs-common" >> $(CONTROL)
	echo "Depends: python3(>= $(MIN_PYTHON_VER)), nfs-common" >> $(CONTROL)

	dpkg-deb --build $(BUILD_DIR)

	cp *.deb ./install && rm -f *.deb
	rm -rf $(BUILD_DIR)

rpm-build:
	rm -rf $(BUILD_DIR)

	python3 $(PYTHON_MERGE_SCRIPT) ./src $(BUILD_DIR)/rpm/SOURCES/$(MOUNT_SCRIPT)
	
	echo "Name: $(NAME)" > $(REDHAT_SPEC)
	echo "Version: $(APP_VERSION)" >> $(REDHAT_SPEC)
	echo "Release: $(RPM_RELEASE_NUM)" >> $(REDHAT_SPEC)
	echo "Summary: $(DESCRIPTION)" >> $(REDHAT_SPEC)
	echo "License: $(LICENSE)" >>  $(REDHAT_SPEC)
	echo "BuildArch: $(RPM_ARCH)" >>  $(REDHAT_SPEC)

	#echo "Requires: python3 >= $(MIN_PYTHON_VER)" >> $(REDHAT_SPEC)
	#echo "Requires: nfs-utils >= 2.6.2" >> $(REDHAT_SPEC)
	#echo "Requires: strongswan >= $(MIN_STRONGSWAN_VER)" >> $(REDHAT_SPEC)

	echo "%define _rpmfilename $(NAME)-$(APP_VERSION).rpm" >> $(REDHAT_SPEC)

	echo "%build" >> $(REDHAT_SPEC)

	echo "%install" >> $(REDHAT_SPEC)
	echo "mkdir -p %{buildroot}/sbin" >> $(REDHAT_SPEC)
	echo "cp %{_sourcedir}/$(MOUNT_SCRIPT) %{buildroot}/sbin" >> $(REDHAT_SPEC)

	echo "%description" >> $(REDHAT_SPEC)
	echo "%files" >> $(REDHAT_SPEC)
	echo "%attr(755, root, root)   $(MOUNT_SCRIPT)" >> $(REDHAT_SPEC)

	rpmbuild -ba  --build-in-place --define "_topdir $(PWD)/$(BUILD_DIR)/rpm" $(REDHAT_SPEC)
	cp  $(BUILD_DIR)/rpm/RPMS/* ./install

	rm -rf $(BUILD_DIR)

local:
	python3 $(PYTHON_MERGE_SCRIPT) ./src /sbin/mount.ibmshare

test:
	cd test && ./run_test.sh
	rm -rf ./src/__pycache__ ./test/__pycache__

pyenv-test:
	cd test && ./run_pyenv_test.sh

clean:
	rm -rf $(BUILD_DIR)
	rm -rf ./src/__pycache__
	rm -rf ./test/__pycache__
	rm -f ./install/*.rpm
	rm -f ./install/*.deb
	rm -rf ./install/certs
	mkdir ./install/certs
	rm -f ./install/*_*.sh
	rm -rf *.gz

_dev:
	cp -r ./certs/dev/* ./install/certs
	python3 $(PYTHON_MERGE_SCRIPT) ./src "GENERATE_CONFIG"
	sed -i "s/region=/region=all/" ./install/share.conf
	sed -i '1s/^/# Dev Environment certs\n/' ./install/share.conf
	sed -i -e '$$a\\ncertificate_duration_seconds=3600' ./install/share.conf
	cd install && tar -czvf  ../$(INSTALL_TAR_FILE)  *
	sha256sum ./$(INSTALL_TAR_FILE) > $(CHECKSUM_FILE)
	@printf "Dev - Install package created ok: $(INSTALL_TAR_FILE)\n"

_prod:
	cp -r ./certs/prod/* ./install/certs
	python3 $(PYTHON_MERGE_SCRIPT) ./src "GENERATE_CONFIG"
	sed -i "s/region=/region=all/" ./install/share.conf
	sed -i -e '$$a\\ncertificate_duration_seconds=3600' ./install/share.conf
	cd install && tar -czvf  ../$(INSTALL_TAR_FILE)  *
	sha256sum ./$(INSTALL_TAR_FILE) > $(CHECKSUM_FILE)
	@printf "Production - Install package created ok: $(INSTALL_TAR_FILE)\n"

build-rpm: clean rpm-build _prod

build-deb: clean deb-build _prod

dev: clean deb-build rpm-build _dev

prod: clean deb-build rpm-build _prod

.PHONY : install
.PHONY : test
