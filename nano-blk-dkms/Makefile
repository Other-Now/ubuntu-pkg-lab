# nano_blk, packaged for DKMS.
#
#   make                       # module, against the running kernel's headers
#   make KDIR=/lib/modules/6.8.0-90-generic/build
#   make blkcheck              # the userspace checker (what debian/rules builds)
#
# DKMS calls the module build itself (see debian/nano-blk-dkms.dkms); the
# Debian build only compiles blkcheck, because a package build has no kernel
# headers and must not depend on the build machine's kernel.
obj-m := nano_blk.o

KDIR ?= /lib/modules/$(shell uname -r)/build

all: module

module:
	$(MAKE) -C $(KDIR) M=$(CURDIR) modules

blkcheck: tools/blkcheck.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -Wall -Wextra $(LDFLAGS) -o $@ $<

clean:
	rm -f blkcheck
	[ ! -d $(KDIR) ] || $(MAKE) -C $(KDIR) M=$(CURDIR) clean

.PHONY: all module clean
