To set up a customized Docker image of RStudio follow the instructions below.

NOTE: the use of '~/git' assumes that the git repositories are stored in the user's home directory, i.e., /home/{USER}/git

```Shell
# build the image {wur_rstudio} from the Dockerfile in ’~git/dsr-qualitative-use/docker_wur_rstudio'
docker build -t wur_rstudio .
# to run an instance of wur_rstudio, i.e. RStudio
docker run --rm -p 8787:8787 -v ~/git:/home/rstudio wur_rstudio
```
RStudio can now be accessed through the browser:
```
http://localhost:8787/
username: rstudio
password: rstudio
```
The terminal/bash of the current container can be accessed as follows:
```
# to switch to the bash of the current container
docker exec -it $(docker ps -a | grep wur_rstudio | awk '{print $1}') bash
```
