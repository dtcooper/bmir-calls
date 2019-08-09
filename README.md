# BMIR Call Routing Software

Here's the [Flask](https://palletsprojects.com/p/flask/) app that routes calls
to and from Burning Man Information Radio (BMIR), for both the broadcast desk
(the "broadcast phone") and the in-lounge hotline (the "weirdness phone") via
[Twilio](https://www.twilio.com/).

Here's a [link to the Google form](https://calls.bmir.org/) where you can enroll.

## Development

You'll need Docker and docker-compose installed.
([Docker for Mac](https://docs.docker.com/docker-for-mac/install/) bundles
both.) Then,

```bash
# Build the containers
docker-compose build

# Initialize the database
docker-compose run app flask init-db
```

Now to run the application which should be available at http://127.0.0.1:5000/

```bash
# Brings up the server (will auto-reload for development)
docker-compose up

# Runs unit tests
docker-compose run app pytest

# Enter the container to run the server manually (must listen on 0.0.0.0)
docker-compose run app bash
flask run -h 0.0.0.0
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.
