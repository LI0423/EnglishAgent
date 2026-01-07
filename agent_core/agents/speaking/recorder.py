import wave
import sounddevice as sd

class InteractiveRecorder:
    def __init__(self, file_name: str = "audio.wav", fs = 16000, channels = 1):
        self.file_name = file_name
        self.fs = fs
        self.channels = channels
        self.recording = []
        self.is_recording = False
        self.stream = None

    def _callback(self, indata, frames, time, status):
        if self.is_recording:
            self.recording.append(indata.copy())
    
    def start_recording(self):
        self.recording = []
        self.is_recording = True
        self.stream = sd.InputStream(
            samplerate=self.fs,
            channels=self.channels,
            callback=self._callback
        )
        self.stream.start()
        print("开始录音，按Enter停止...")

    def stop_recording(self):
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        audio_data = b''.join([d.tobytes() for d in self.recording])
        with wave.open(self.file_name, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.fs)
            wf.writeframes(audio_data)
        print(f'录音结束，已保存为 {self.file_name}')
        return self.file_name
    
    