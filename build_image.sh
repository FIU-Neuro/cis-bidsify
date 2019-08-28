# chmod stuff
chmod 775 *.py
chmod 775 *.sh

docker build -t cis/bidsify:v0.1.0 .

# This converts the Docker image cis/bidsify to a singularity image,
# to be located in /Users/tsalo/Documents/singularity_images/
docker run --privileged -t --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /Users/tsalo/Documents/singularity_images:/output \
  singularityware/docker2singularity \
  -m "/scratch" \
  cis/bidsify:v0.1.0
