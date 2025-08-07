# DAG Design Documentation


## Development Notes / Design Decisions

1. I have configured XCOM to use a shared file system rather than the default database. this allows us to pass more data between tasks
2. For development, I am running two postgresql servers, as my model migration scripts were intefereing with the default apache airflow tables
3. I have edited the docker compose file to limit the resources in my development environment. For Production we will need to Tune and adjust the env variables
4. I have used default usernames and passwords, all databases and services will need better security


