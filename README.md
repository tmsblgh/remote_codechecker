# Remote CodeChecker

Diagram about the concept

<a>
  <img src="sequence_diagram.svg">
</a>

## Getting Started

### macOS

Go through on the Docker for Mac installation guide:
https://docs.docker.com/docker-for-mac/install/

#### CodeChecker part

```sh
# Check out my forked CodeChecker source code.
git clone https://github.com/tmsblgh/codechecker
cd codechecker

# Build Docker container in it.
docker build -t codechecker .
```

#### Remote CodeChecker part

```sh
# Check out my forked CodeChecker source code.
git clone https://github.com/tmsblgh/remote_codechecker
cd remote_codechecker

# Build Docker container in it.
docker build -t remote_codechecker .

# Build Redis container and start all previously created container for the service.
docker-compose up

# Start an analyze with the provided test resources
python3 remote_analyze.py analyze -cdb ../test/compile_commands.json
```

## Notes

Files from other repositories:

client/tu_collector.py is a copy from the original CodeChecker repository
(https://github.com/Ericsson/codechecker)