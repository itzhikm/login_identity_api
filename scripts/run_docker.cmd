@echo off
setlocal
pushd "%~dp0.."

docker build -t login_identity_api . || goto :fail


echo Running login_identity_api
docker run --rm --add-host=host.docker.internal:host-gateway -p 8000:8000 --env-file .env login_identity_api || goto :fail

popd
endlocal & exit /b 0

:fail
popd
endlocal & exit /b 1