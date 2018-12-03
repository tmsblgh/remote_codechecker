ACTIVATE_RUNTIME_VENV ?= . venv/bin/activate
VENV_REQ_FILE ?= requirements_py.txt

venv:
	virtualenv venv && \
		$(ACTIVATE_RUNTIME_VENV) && pip install -r $(VENV_REQ_FILE)

clean_venv:
	rm -rf venv