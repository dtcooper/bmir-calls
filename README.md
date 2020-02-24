# BMIR Call Routing Software

Here's the [Flask](https://palletsprojects.com/p/flask/) app that routes calls
to and from [Burning Man Information Radio (BMIR)](https://bmir.org), for both
the broadcast desk (the "broadcast phone") and our new for 2019, in-lounge
hotline (the "BMIR Phone Experiment" or "weirdness" phone) via
[Twilio](https://www.twilio.com/).

Here's a [link to the Google form](https://calls.bmir.org/) where you can enroll.

## Running via docker-compose

Getting the project up and running is pretty easy. You'll need
[Docker](https://www.docker.com/) and
[docker-compose](https://docs.docker.com/compose/) installed.
([Docker for Mac](https://docs.docker.com/docker-for-mac/install/) bundles
both.) Then,

```bash
# Clone the repo
git clone https://github.com/dtcooper/bmir-calls.git
cd bmir-calls

# Build the containers, initialize the database
docker-compose build
docker-compose run app flask init-db

# Run the unit tests
docker-compose run app pytest
```

Run the application which'll then be available at
[127.0.0.1:5000](http://127.0.0.1:5000/).

```bash
# Brings up the server (will auto-reload for development)
docker-compose up

# Or enter the container to run the server manually, useful for development,
# using a debugger, using the Python shell, etc
docker-compose run --service-ports app bash
flask run
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.
