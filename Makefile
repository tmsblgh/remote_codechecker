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
	$(ACTIVATE_DEV_VENV) && pycodestyle server client

pylint: venv_dev
	$(ACTIVATE_DEV_VENV) && pylint server client

clean_venv:
	rm -rf venv

clean_venv_dev:
	rm -rf venv_dev
