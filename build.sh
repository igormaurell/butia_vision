#!/bin/bash

IMAGE_NAME="ghcr.io/butia-bots/butia_vision"

nvidia-docker build -t --gpus all ${IMAGE_NAME} .