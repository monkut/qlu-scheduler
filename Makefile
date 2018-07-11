check:
	flake8 --max-line-length 140 --max-complexity 10 qlu/
	pydocstyle qlu/

pylint:
	pylint --rcfile .pylintrc qlu/

typecheck:
	mypy  qlu/ --disallow-untyped-defs --silent-imports

test:
	pytest -v tests

coverage:
	pytest --cov qlu/ --cov-report term-missing

htmlcov:
	pytest --cov qlu/ --cov-report html
	open /tmp/htmlcov/index.html

pullrequestcheck: check pylint coverage
