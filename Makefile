build:
	docker build -f Dockerfile -t ftp-duplicator .

debug: build
	docker run -i -t ftp-duplicator bash
