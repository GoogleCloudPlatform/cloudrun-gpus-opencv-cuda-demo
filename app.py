# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import uuid
import logging
from flask import Flask, request, jsonify, send_from_directory
from pipeline import pipeline_executor, gpu_pipeline, cpu_pipeline
from werkzeug.utils import secure_filename

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

RESIZED_FRAME = '800x600'

app = Flask(
    __name__,
    instance_relative_config=True,
    template_folder="templates",
)

@app.route("/version", methods=["GET"])
def version():
    return jsonify({
        "version": "2024.07.12"
        })

@app.route("/", methods=["GET"])
def home():
    # open index.html and return it
    with open("templates/index.html") as f:
        return f.read()

@app.route('/videos/<filename>')
def uploaded_file(filename):
    return send_from_directory("videos", filename,
                               conditional=True)    


@app.route("/process", methods=["POST"])
def process():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file uploaded'}), 400

    saved_filename = secure_filename(str(uuid.uuid4()) + '.mp4')
    saved_filepath = os.path.join('videos', saved_filename)

    try:
        request.files['video'].save(saved_filepath)
    except Exception as e:
        logging.error('Error saving video: %s', e)
        return jsonify({'error': 'Error saving video'}), 500

    device = request.form.get('pipeline', 'gpu').lower()
    post_processing = request.form.get('post_processing', 'both').upper()
    video_resolution = request.form.get('video_resolution', RESIZED_FRAME).lower()

    resized_frame_width = int(video_resolution.split('x')[0])
    resized_frame_height = int(video_resolution.split('x')[1])

    if device == pipeline_executor.PipelineType.GPU:
        pipeline = gpu_pipeline.GPUProcessingPipeline(
            resized_frame_width, 
            resized_frame_height, 
            pipeline_executor.PipelinePostProcessingOptions[post_processing.upper()]
        )
    elif device == pipeline_executor.PipelineType.CPU:
        pipeline = cpu_pipeline.CPUProcessingPipeline(
            resized_frame_width, 
            resized_frame_height, 
            pipeline_executor.PipelinePostProcessingOptions[post_processing.upper()]
        )
    else:
        logging.error('Invalid pipeline type: %s', device)
        return jsonify({'error': 'Invalid pipeline type'}), 500
        

    output, http_code = pipeline_executor.PipelineExecutor().execute(pipeline=pipeline, filepath=saved_filepath)

    # remove original video
    os.remove(saved_filepath)

    return jsonify(output), http_code
