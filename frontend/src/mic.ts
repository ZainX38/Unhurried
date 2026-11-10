// Live microphone -> 16 kHz PCM16 frames (see public/pcm-worklet.js).

export async function startMic(
  ctx: AudioContext,
  onFrame: (frame: Int16Array) => void,
): Promise<() => void> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true, // the bot's voice from the speakers mustn't count as the caller talking
      noiseSuppression: true,
      autoGainControl: false, // AGC lifts the noise floor in pauses, which the energy VAD would hear as speech
    },
  });
  try {
    await ctx.audioWorklet.addModule("/pcm-worklet.js");
  } catch (err) {
    stream.getTracks().forEach((t) => t.stop());
    throw err;
  }
  const source = ctx.createMediaStreamSource(stream);
  // No outputs: nothing is played back, and Chrome still runs a node with no outputs.
  const node = new AudioWorkletNode(ctx, "pcm16-frames", { numberOfInputs: 1, numberOfOutputs: 0 });
  node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => onFrame(new Int16Array(e.data));
  source.connect(node);

  return () => {
    node.port.onmessage = null;
    source.disconnect();
    stream.getTracks().forEach((t) => t.stop());
  };
}
