build:
	docker build -f Dockerfile -t ftp-duplicator .

debug: build
	docker run -i -p 20:20 -p 21:21 -p 21100-21110:21100-21110 -t ftp-duplicator bash
