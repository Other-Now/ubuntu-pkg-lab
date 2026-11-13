# Publishing nano-blk to a Launchpad PPA

**Status: not done.** It needs a Launchpad account with an OpenPGP key registered
and the Ubuntu Code of Conduct signed.  Everything below is the procedure, not
something that has been run.

## One-time setup

1. Create a Launchpad account and a PPA, e.g. `ppa:<lp-user>/nano-blk`.
2. Generate an OpenPGP key (`gpg --full-generate-key`), upload it to
   `keyserver.ubuntu.com`, and add its fingerprint on Launchpad.
3. `sudo apt install devscripts dput`

## Upload

Launchpad builds from **source** uploads only.  Binary .debs are never uploaded,
and its builders produce one nano-blk-tools per architecture enabled for the PPA
(amd64 and arm64 by default; ppc64el, s390x and riscv64 can be enabled).

```sh
cd nano-blk-dkms
debuild -S -sa -k<KEYID>          # signed .dsc + _source.changes; -sa includes the full source
dput ppa:<lp-user>/nano-blk ../nano-blk_0.1.1_source.changes
```

A native package has no orig tarball, so every upload carries the full source.

For another release (e.g. jammy), add a changelog entry with a distinct
version.  Each version can only be uploaded once per PPA:

```sh
dch -v 0.1.1~22.04.1 -D jammy "Rebuild for jammy."
```

## Install, once published

```sh
sudo add-apt-repository ppa:<lp-user>/nano-blk
sudo apt install nano-blk-dkms nano-blk-tools
```
