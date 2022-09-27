container:
	buildah build -t ghcr.io/jelmer/litegpodder .
	buildah push ghcr.io/jelmer/litegpodder
