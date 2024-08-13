/*
Copyright 2024 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

const recording_origin = document.getElementById('recording_origin');
const recording_output = document.getElementById('recording_output');
const start_button = document.getElementById('start_button');
const reset_button = document.getElementById('reset_button');
const status_table = document.getElementById('status_table');
const inputDeviceSelection = document.getElementById('input_device_selection');
const codecSelect = document.getElementById('codec_select');

let g_Recording = false;
let g_mediaRecorder;
let g_captureDeviceID = 0;

window.onload = (event) => {
  if (navigator.mediaDevices) {
    navigator.mediaDevices.enumerateDevices()
      .then(devices => {
        const videoDevices = devices.filter(device => device.kind === 'videoinput');
        var idx = 0;

        videoDevices.forEach(device => {
          const option_div = document.createElement('div');
          option_div.className = "input-radio";
          
          const option_input = document.createElement('input');
          option_input.value = device.deviceId;
          option_input.id = "camera_select_" + idx;
          option_input.name = "camera_select";
          option_input.type = "radio";
          option_input.checked = idx == 0 ? true : false;

          const option_label = document.createElement('label');
          option_label.innerHTML = device.label || `Camera ${idx}`;
          option_label.htmlFor = option_input.id;

          option_div.appendChild(option_input);
          option_div.appendChild(option_label);

          inputDeviceSelection.appendChild(option_div);
          idx++;
        });
      })
      .catch(error => {
        console.error('Error enumerating devices:', error);
      });

      inputDeviceSelection.addEventListener('change', (event) => {
      g_captureDeviceID = event.target.value;
      console.log(g_captureDeviceID);
      navigator.mediaDevices.getUserMedia({ video: { deviceId: g_captureDeviceID } })
        .then(stream => {
          recording_origin.srcObject = stream;
        })
        .catch(error => {
          console.error('Error accessing selected camera:', error);
        });
    });

    const supportedCodecs = [
      'video/mp4; codecs=vp8',
      'video/mp4; codecs=vp9',
      'video/mp4; codecs=opus',
      'video/mp4; codecs=av1',
      'video/mp4; codecs=avc1',
      'video/mp4; codecs=hevc',
      'video/mp4; codecs=hvc1',
      'video/mp4; codecs=h264',
      'video/mp4; codecs=h265',
      'video/webm',
    ];

    supportedCodecs.forEach(codec => {
      if (MediaRecorder.isTypeSupported(codec)) {
        const option = document.createElement('option');
        option.value = codec;
        option.text = codec;
        codecSelect.appendChild(option);        
      }
      console.log(codec + ' is not supported');
    });

    codecSelect.addEventListener('change', (event) => {
      g_mediaRecorder.options = { 
        audioBitsPerSecond: 128000,
        videoBitsPerSecond: 2500000,
        mimeType: event.target.value
      }
    });

    navigator.mediaDevices.getUserMedia({ video: {deviceId: g_captureDeviceID} })
    .then(stream => {
      recording_origin.srcObject = stream;
    })
    .catch(error => {
      console.error('Error accessing webcam:', error);
    });

  } else {
    alert('Video capture is not supported on this device.');
  }
}

function startRecording() {
  if (navigator.mediaDevices) {
    navigator.mediaDevices.getUserMedia({ video: {deviceId: g_captureDeviceID} })
      .then(stream => {
        const options = {
          audioBitsPerSecond: 128000,
          videoBitsPerSecond: 2500000,
          mimeType: codecSelect.value,
        };
        
        g_mediaRecorder = new MediaRecorder(stream, options);
        g_mediaRecorder.ondataavailable = handleDataAvailable;
        g_mediaRecorder.start();
        
        recording_origin.srcObject = stream;
        g_Recording = true;
        start_button.textContent = '■ Stop Recording';

      })
      .catch(error => {
        console.error('Error accessing webcam:', error);
      });
  } else {
    alert('Webcam not supported on your device.');
  }
}

function stopRecording() {
  g_mediaRecorder.stop();
  g_Recording = false;
}

function handleDataAvailable(event) {
  var pipeline = '';
  var els = document.getElementsByName('pipeline');
  for (var i=0;i<els.length;i++){
    if ( els[i].checked ) {
      pipeline = els[i].value;
    }
  }
  
  var post_processing = '';
  var els = document.getElementsByName('post_processing');
  for (var i=0;i<els.length;i++){
    if ( els[i].checked ) {
      post_processing = els[i].value;
    }
  }  

  const formData = new FormData();
  formData.append('video', event.data);
  formData.append('pipeline', pipeline)
  formData.append('post_processing', post_processing)
  formData.append('video_resolution', document.getElementById('video_resolution').value)

  start_button.setAttribute('disabled', 'true')
  start_button.textContent = 'Processing... please wait'

  fetch('/process', {
    method: 'POST',
    body: formData
  })
  .then((response) => response.json())
  .then((data) => {
    start_button.removeAttribute('disabled')
    start_button.textContent = '► Start recording'  
    document.getElementsByClassName('feature__actions')[0].style.display = 'none';
    document.getElementsByClassName('feature__result')[0].style.display = 'block';


    if(data.error) {
      alert(data.error)
      return;
    }

    if(!data.video) {
      alert('No video was generated. Check the logs.')
      return;
    }

    var currentDate = new Date(); 
    tbody = status_table.getElementsByTagName('tbody')[0];
    let row = tbody.insertRow();
    
    cell = row.insertCell();
    cell.appendChild(document.createTextNode(currentDate.getHours() + ":"  + currentDate.getMinutes() + ":" + currentDate.getSeconds()));
    cell = row.insertCell();
    cell.appendChild(document.createTextNode(data.device));

    for (const [key, value] of Object.entries(data.stats)) {
      cell = row.insertCell();
      cell.appendChild(document.createTextNode(value)); 
    }

    // update the video source to the new video
    recording_output.pause();
    v_src = recording_output.getElementsByTagName('source')[0];
    v_src.src = data.video;
    recording_output.load();
    recording_output.play();
  })
  .catch(error => {
    console.error('Error sending video:', error);
  });
}

start_button.addEventListener('click', () => {
  if (g_Recording) {
    stopRecording();
  } else {
    startRecording();
  }
});

reset_button.addEventListener('click', () => {
  document.getElementsByClassName('feature__result')[0].style.display = 'none';
  document.getElementsByClassName('feature__actions')[0].style.display = 'flex';
});

