# Local setup

Use Git, Make, Node 22 LTS, npm 10+, uv 0.11.12 and Docker Desktop with a running
native ARM64 engine. The project selects Python 3.12 independently of the host's
default Python. The Docker engine needs enough resources for the database, web,
API and one headless worker; the verified machine's engine has about 8 GB RAM.

```sh
cd /Users/redmug/EARTHMIND
make setup
make dev
make status
make smoke
```

Setup validates tools and Docker architecture, preserves existing `.env`, creates
random local credentials for a new configuration, installs locked dependencies,
and installs pre-commit hooks. Dev builds and starts the complete stack, applies
migrations through one controlled service, waits for health, verifies image
architectures and runs the deployment smoke check.

Open http://localhost:3000 and http://localhost:8000/docs. PostgreSQL listens on
127.0.0.1:5434. Redis is private. Override only the documented port settings in
`.env` when needed. Changing the environment password does not rotate a password
already stored inside an initialized PostgreSQL volume.

`make down` stops only this project's services and preserves named volumes.
`make clean` removes only known disposable build/test caches. Neither removes
datasets, credentials or database volumes.

For authorized aerial imagery and Cesium OSM Buildings, follow the
[Cesium ion configuration and restart guide](cesium-ion-integration.md).
`NEXT_PUBLIC_CESIUM_ION_TOKEN` is the canonical public visualization setting;
keep its value only in ignored local environment files. Select Realistic City
in the existing Explorer mode control after the web service is recreated.
