check:
	pipenv run flake8 --max-line-length 150 --max-complexity 18 qlu/

pylint:
	pipenv run pylint --rcfile .pylintrc qlu/

typecheck:
	pipenv run mypy  qlu/ --disallow-untyped-defs --silent-imports

test:
	pipenv run pytest -v tests

coverage:
	pipenv run pytest --cov qlu/ --cov-report term-missing

htmlcov:
	pipenv run pytest --cov qlu/ --cov-report html
	open /tmp/htmlcov/index.html

pullrequestcheck: check coverage
