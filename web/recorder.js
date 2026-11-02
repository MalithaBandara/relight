// Microphone recorder for the demo pages: one utterance as a 16 kHz mono WAV (what Voice Transcribe takes).
// It stops by itself after a pause (SILENCE_S) or after MAX_S, or when stop() is called.
const Recorder = (() => {
  const RATE = 16000, SILENCE_S = 1.4, MAX_S = 25, SPEECH_RMS = 0.015;

  function wavBlob(chunks, inRate) {
    let len = 0; for (const c of chunks) len += c.length;
    const all = new Float32Array(len); let o = 0;
    for (const c of chunks) { all.set(c, o); o += c.length; }
    const ratio = inRate / RATE, n = Math.floor(len / ratio), pcm = new Int16Array(n);
    for (let i = 0; i < n; i++) {   // average each window of source samples: a plain low-pass before dropping to 16 kHz
      const a = Math.floor(i * ratio), b = Math.max(a + 1, Math.min(len, Math.floor((i + 1) * ratio)));
      let s = 0; for (let j = a; j < b; j++) s += all[j];
      pcm[i] = Math.max(-1, Math.min(1, s / (b - a))) * 32767;
    }
    const buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
    const str = (p, t) => { for (let i = 0; i < t.length; i++) v.setUint8(p + i, t.charCodeAt(i)); };
    str(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); str(8, "WAVEfmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
    v.setUint16(22, 1, true); v.setUint32(24, RATE, true); v.setUint32(28, RATE * 2, true); v.setUint16(32, 2, true);
    v.setUint16(34, 16, true); str(36, "data"); v.setUint32(40, n * 2, true);
    new Int16Array(buf, 44).set(pcm);
    return new Blob([buf], { type: "audio/wav" });
  }

  // start({onLevel(0..1), onDone({blob, heard})}) -> handle for stop() / cancel()
  async function start({ onLevel, onDone }) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw new Error("This browser cannot use the microphone here. Type instead.");
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } }); }
    catch (err) { throw new Error(err.name === "NotAllowedError" ? "The microphone is blocked for this page. Allow it in the browser, or type instead." : err.message); }
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const src = ctx.createMediaStreamSource(stream), proc = ctx.createScriptProcessor(4096, 1, 1);
    const rec = { stream, ctx, proc, chunks: [], heard: false, quiet: 0, secs: 0, finished: false };
    const finish = (send) => {
      if (rec.finished) return;
      rec.finished = true;
      proc.onaudioprocess = null; proc.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      const rate = ctx.sampleRate; ctx.close();
      if (onLevel) onLevel(0);
      if (send && onDone) onDone({ blob: rec.heard ? wavBlob(rec.chunks, rate) : null, heard: rec.heard });
    };
    rec.stop = () => finish(true);
    rec.cancel = () => finish(false);
    proc.onaudioprocess = (e) => {
      const d = new Float32Array(e.inputBuffer.getChannelData(0));
      rec.chunks.push(d);
      let s = 0; for (let i = 0; i < d.length; i++) s += d[i] * d[i];
      const rms = Math.sqrt(s / d.length), dt = d.length / ctx.sampleRate;
      rec.secs += dt;
      if (onLevel) onLevel(Math.min(1, rms * 12));
      if (rms > SPEECH_RMS) { rec.heard = true; rec.quiet = 0; } else if (rec.heard) rec.quiet += dt;
      if ((rec.heard && rec.quiet >= SILENCE_S) || rec.secs >= MAX_S) rec.stop();
    };
    src.connect(proc); proc.connect(ctx.destination);   // the processor writes no output, so nothing is played back
    return rec;
  }

  return { start, wavBlob };
})();
