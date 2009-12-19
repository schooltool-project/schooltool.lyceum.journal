#!/usr/bin/make
#
# Makefile for schooltool.lyceum.journal Buildout
#

BOOTSTRAP_PYTHON=python2.5
INSTANCE_TYPE=schooltool
BUILDOUT_FLAGS=

.PHONY: all
all: build

.PHONY: build
build: bin/test

.PHONY: bootstrap
bootstrap bin/buildout:
	$(BOOTSTRAP_PYTHON) bootstrap.py

.PHONY: buildout
buildout bin/test: bin/buildout setup.py base.cfg buildout.cfg
	bin/buildout $(BUILDOUT_FLAGS)
	@touch --no-create bin/test

.PHONY: update
update: bin/buildout
	bzr up
	$(MAKE) buildout BUILDOUT_FLAGS=-n

.PHONY: test
test: build
	bin/test -u

.PHONY: ftest
ftest: build
	bin/test -f

.PHONY: testall
testall: build
	bin/test --at-level 2

instance:
	$(MAKE) buildout
	bin/make-schooltool-instance instance instance_type=$(INSTANCE_TYPE)

.PHONY: run
run: build instance
	bin/start-schooltool-instance instance

.PHONY: release
release: bin/buildout
	echo -n `cat version.txt.in`_r`bzr revno` > version.txt
	bin/buildout setup setup.py sdist

.PHONY: move-release
move-release:
	mv -v dist/schooltool.lyceum.journal-*.tar.gz /home/ftp/pub/schooltool/1.2/dev

.PHONY: coverage
coverage: build
	test -d parts/test/coverage && ! test -d coverage && mv parts/test/coverage . || true
	rm -rf coverage
	bin/test --at-level 2 -u --coverage=coverage
	mv parts/test/coverage .

.PHONY: coverage-reports-html
coverage-reports-html coverage/reports:
	test -d parts/test/coverage && ! test -d coverage && mv parts/test/coverage . || true
	rm -rf coverage/reports
	mkdir coverage/reports
	bin/coverage coverage coverage/reports
	ln -s schooltool.lyceum.journal.html coverage/reports/index.html

.PHONY: ftest-coverage
ftest-coverage: build
	test -d parts/test/ftest-coverage && ! test -d ftest-coverage && mv parts/test/ftest-coverage . || true
	rm -rf ftest-coverage
	bin/test --at-level 2 -f --coverage=ftest-coverage
	mv parts/test/ftest-coverage .

.PHONY: ftest-coverage-reports-html
ftest-coverage-reports-html ftest-coverage/reports:
	test -d parts/test/ftest-coverage && ! test -d ftest-coverage && mv parts/test/ftest-coverage . || true
	rm -rf ftest-coverage/reports
	mkdir ftest-coverage/reports
	bin/coverage ftest-coverage ftest-coverage/reports
	ln -s schooltool.lyceum.journal.html ftest-coverage/reports/index.html

.PHONY: clean
clean:
	rm -f version.txt
	rm -rf bin develop-eggs parts python
	rm -rf build dist
	rm -f .installed.cfg
	rm -f ID TAGS tags
	find . -name '*.py[co]' -exec rm -f {} \;
	find . -name '*.mo' -exec rm -f {} +
	find . -name 'LC_MESSAGES' -exec rmdir -p --ignore-fail-on-non-empty {} +

.PHONY: realclean
realclean: clean
	rm -rf eggs
	rm -rf instance

.PHONY: extract-translations
extract-translations: build
	bin/i18nextract --egg schooltool.lyceum.journal \
	                --domain schooltool.lyceum.journal \
	                --zcml schooltool/lyceum/journal/translations.zcml \
	                --output-file src/schooltool/lyceum/journal/locales/schooltool.lyceum.journal.pot

.PHONY: compile-translations
compile-translations:
	set -e; \
	locales=src/schooltool/lyceum/journal/locales; \
	for f in $${locales}/*.po; do \
	    mkdir -p $${f%.po}/LC_MESSAGES; \
	    msgfmt -o $${f%.po}/LC_MESSAGES/schooltool.lyceum.journal.mo $$f;\
	done

.PHONY: update-translations
update-translations: extract-translations
	set -e; \
	locales=src/schooltool/lyceum/journal/locales; \
	for f in $${locales}/*.po; do \
	    msgmerge -qU $$f $${locales}/schooltool.lyceum.journal.pot ;\
	done
	$(MAKE) compile-translations

.PHONY: ubuntu-environment
ubuntu-environment:
	@if [ `whoami` != "root" ]; then { \
	 echo "You must be root to create an environment."; \
	 echo "I am running as $(shell whoami)"; \
	 exit 3; \
	} else { \
	 apt-get install bzr build-essential python-all python-all-dev libc6-dev libicu-dev; \
	 apt-get build-dep python-imaging; \
	 echo "Installation Complete: Next... Run 'make'."; \
	} fi
