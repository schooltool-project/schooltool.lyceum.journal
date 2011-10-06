#!/usr/bin/make

PACKAGE=schooltool.lyceum.journal

DIST=/home/ftp/pub/schooltool/flourish
BOOTSTRAP_PYTHON=python2.6

INSTANCE_TYPE=schooltool
BUILDOUT_FLAGS=

.PHONY: all
all: build

.PHONY: build
build: .installed.cfg

.PHONY: bootstrap
bootstrap bin/buildout python:
	$(BOOTSTRAP_PYTHON) bootstrap.py

.PHONY: buildout
buildout .installed.cfg: python bin/buildout buildout.cfg base.cfg setup.py
	bin/buildout $(BUILDOUT_FLAGS)

.PHONY: update
update:
	bzr up
	$(MAKE) buildout BUILDOUT_FLAGS=-n

instance: | build
	bin/make-schooltool-instance instance instance_type=$(INSTANCE_TYPE)

.PHONY: run
run: build instance
	bin/start-schooltool-instance instance

.PHONY: tags
tags: build
	bin/tags

.PHONY: clean
clean:
	rm -rf python
	rm -rf bin develop-eggs parts .installed.cfg
	rm -rf build
	rm -f ID TAGS tags
	rm -rf coverage ftest-coverage
	find . -name '*.py[co]' -delete
	find . -name '*.mo' -delete
	find . -name 'LC_MESSAGES' -exec rmdir -p --ignore-fail-on-non-empty {} +

.PHONY: realclean
realclean:
	rm -rf eggs
	rm -rf dist
	rm -rf instance
	$(MAKE) clean

# Tests

.PHONY: test
test: build
	bin/test -u

.PHONY: ftest
ftest: build
	bin/test -f

.PHONY: testall
testall: build
	bin/test --at-level 2

# Coverage

.PHONY: coverage
coverage: build
	test -d parts/test/coverage && ! test -d coverage && mv parts/test/coverage . || true
	rm -rf coverage
	bin/test --at-level 2 -u --coverage=coverage
	mv parts/test/coverage .

.PHONY: coverage-reports-html
coverage-reports-html coverage/reports: coverage
	test -d parts/test/coverage && ! test -d coverage && mv parts/test/coverage . || true
	rm -rf coverage/reports
	mkdir coverage/reports
	bin/coverage coverage coverage/reports
	ln -s $(PACKAGE).html coverage/reports/index.html

.PHONY: ftest-coverage
ftest-coverage: build
	test -d parts/test/ftest-coverage && ! test -d ftest-coverage && mv parts/test/ftest-coverage . || true
	rm -rf ftest-coverage
	bin/test --at-level 2 -f --coverage=ftest-coverage
	mv parts/test/ftest-coverage .

.PHONY: ftest-coverage-reports-html
ftest-coverage-reports-html ftest-coverage/reports: ftest-coverage
	test -d parts/test/ftest-coverage && ! test -d ftest-coverage && mv parts/test/ftest-coverage . || true
	rm -rf ftest-coverage/reports
	mkdir ftest-coverage/reports
	bin/coverage ftest-coverage ftest-coverage/reports
	ln -s $(PACKAGE).html ftest-coverage/reports/index.html

# Translations

.PHONY: extract-translations
extract-translations: build
	bin/i18nextract --egg $(PACKAGE) \
	                --domain $(PACKAGE) \
	                --zcml schooltool/lyceum/journal/translations.zcml \
	                --output-file src/schooltool/lyceum/journal/locales/schooltool.lyceum.journal.pot

.PHONY: compile-translations
compile-translations:
	set -e; \
	locales=src/schooltool/lyceum/journal/locales; \
	for f in $${locales}/*.po; do \
	    mkdir -p $${f%.po}/LC_MESSAGES; \
	    msgfmt -o $${f%.po}/LC_MESSAGES/$(PACKAGE).mo $$f;\
	done

.PHONY: update-translations
update-translations:
	set -e; \
	locales=src/schooltool/lyceum/journal/locales; \
	for f in $${locales}/*.po; do \
	    msgmerge -qUN $$f $${locales}/$(PACKAGE).pot ;\
	done
	$(MAKE) compile-translations

# Release

.PHONY: release
release: compile-translations
	grep -qv 'dev' version.txt.in || echo -n `cat version.txt.in`-r`bzr revno` > version.txt
	python setup.py sdist
	rm -f version.txt

.PHONY: move-release
move-release: upload
	rm -v dist/$(PACKAGE)-*dev-r*.tar.gz

.PHONY: upload
upload:
	@VERSION=`cat version.txt.in` ;\
	DIST=$(DIST) ;\
	grep -qv 'dev' version.txt.in || VERSION=`cat version.txt.in`-r`bzr revno` ;\
	grep -qv 'dev' version.txt.in || DIST=$(DIST)/dev ;\
	if [ -w $${DIST} ] ; then \
	    echo cp dist/$(PACKAGE)-$${VERSION}.tar.gz $${DIST} ;\
	    cp dist/$(PACKAGE)-$${VERSION}.tar.gz $${DIST} ;\
	else \
	    echo scp dist/$(PACKAGE)-$${VERSION}.tar.gz* schooltool.org:$${DIST} ;\
	    scp dist/$(PACKAGE)-$${VERSION}.tar.gz* schooltool.org:$${DIST} ;\
	fi

# Helpers

.PHONY: ubuntu-environment
ubuntu-environment:
	sudo apt-get install bzr build-essential gettext enscript ttf-liberation \
	    python-all-dev libc6-dev libicu-dev libxslt1-dev libfreetype6-dev libjpeg62-dev 

