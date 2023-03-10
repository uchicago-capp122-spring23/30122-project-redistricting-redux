To run this project from the command line, type `poetry shell` to instantiate a poetry shell, then type `poetry run python redistricting_redux`. That will call `__main__.py`, which in turn calls `app.py`. If necessary, download repository to local machine using `git clone` and input command `poetry install` first to get dependencies set up.

As of now, you CANNOT use `python3 -m...`; it WILL NOT work.

This project was created using data from the Redistricting Data Hub, redistrictingdatahub.org.

The process to pull the data from the API and create merged shapefiles is intentionally left out of the above command. In order to run that process, type `poetry run python redistricting_redux/rdh_2020/join_data_to_shp.py` from the command line. You will need a username and password for the Redistricting Data Hub API. Since data is not consistently available/formatted for each state, please note that a very limited selection of states will work. Some examples of states that will work include: AZ, FL *(not included in final project)*, GA, IL *(not included in final project due to substantial missing data)*, NC, NV, OH, and TX. It is possible that modifications in the API/merging scripts might enable a user to created merged shapefiles for other states.
