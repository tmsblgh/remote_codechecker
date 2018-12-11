ACTIVATE_RUNTIME_VENV ?= . venv/bin/activate
ACTIVATE_DEV_VENV ?= . venv_dev/bin/activate
VENV_REQ_FILE ?= requirements_py/requirements.txt
VENV_DEV_REQ_FILE ?= requirements_py/dev/requirements.txt

venv:
	virtualenv venv && \
		$(ACTIVATE_RUNTIME_VENV) && pip3 install -r $(VENV_REQ_FILE)

venv_dev:
	virtualenv venv_dev && \
		$(ACTIVATE_DEV_VENV) && pip3 install -r $(VENV_DEV_REQ_FILE)

pycodestyle: venv_dev
	# ignore E402 module level import not at top of file
	# because of 'sys.path.append('../gen-py')'
	$(ACTIVATE_DEV_VENV) && pycodestyle -v --ignore=E402 server client

pylint: venv_dev
	$(ACTIVATE_DEV_VENV) && pylint --exit-zero server client

check: pylint pycodestyle

build_docker:
	docker build -t remote_codechecker .

clean_venv:
	rm -rf venv

clean_venv_dev:
	rm -rf venv_dev
