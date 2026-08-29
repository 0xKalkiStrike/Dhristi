import { useState } from "react";
import { api } from "../services/api";
import { Spinner } from "./ui";

type Tab = "webcam" | "bluetooth" | "ip";

export function ConnectCamera({ onConnected }: { onConnected: () => void }) {
  const [tab, setTab] = useState<Tab>("webcam");
  const [videoDevs, setVideoDevs] = useState<any[] | null>(null);
  const [btDevs, setBtDevs] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [name, setName] = useState("Live Camera");
  const [index, setIndex] = useState(0);
  const [url, setUrl] = useState("");
  const [probe, setProbe] = useState<Record<number, any>>({});

  const scanVideo = async () => {
    setBusy(true); setMsg("");
    try { setVideoDevs((await api.videoDevices()).devices); }
    catch (e: any) { setMsg(e.message); }
    finally { setBusy(false); }
  };
  const scanBt = async () => {
    setBusy(true); setMsg("");
    try { setBtDevs(await api.bluetoothDevices()); }
    catch (e: any) { setMsg(e.message); }
    finally { setBusy(false); }
  };
  const doProbe = async (i: number) => {
    setMsg(`Probing device ${i} (camera init can take a few seconds)…`);
    try { const r = await api.probeDevice(i); setProbe((p) => ({ ...p, [i]: r }));
          setMsg(r.ok ? `Device ${i}: ${r.width}x${r.height} OK` : `Device ${i}: ${r.error}`); }
    catch (e: any) { setMsg(e.message); }
  };
  const connect = async (payload: any) => {
    setBusy(true); setMsg("Connecting live camera (real detector, no demo data)…");
    try {
      const cam = await api.connectLive(payload);
      setMsg(`✓ Connected ${cam.camera_id}. Live analysis starting (camera warm-up ~a few seconds).`);
      onConnected();
    } catch (e: any) { setMsg(`Error: ${e.message}`); }
    finally { setBusy(false); }
  };

  return (
    <div className="panel p-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="panel-title">Connect Live Camera</div>
        <span className="text-[10px] text-cmd-ok">REAL INPUT · NO DEMO DATA</span>
      </div>

      <div className="flex gap-1">
        {(["webcam", "bluetooth", "ip"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`btn text-xs capitalize ${tab === t ? "btn-primary" : ""}`}>
            {t === "ip" ? "Phone / IP" : t}
          </button>
        ))}
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-[10px] uppercase tracking-wider text-cmd-muted">Camera name</span>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
      </label>

      {tab === "webcam" && (
        <div className="space-y-2">
          <button className="btn w-full" onClick={scanVideo} disabled={busy}>Scan cameras</button>
          {busy && !videoDevs && <Spinner />}
          {videoDevs && videoDevs.length === 0 && <p className="text-xs text-cmd-muted">No OS cameras found.</p>}
          {videoDevs?.map((d) => (
            <div key={d.index} className="flex items-center justify-between gap-2 border border-cmd-border rounded p-2">
              <div className="min-w-0">
                <div className="text-sm text-white truncate">{d.name}</div>
                <div className="text-[10px] text-cmd-muted">index {d.index}{d.is_bluetooth ? " · bluetooth" : ""}
                  {probe[d.index] ? (probe[d.index].ok ? ` · ${probe[d.index].width}x${probe[d.index].height}` : " · unavailable") : ""}</div>
              </div>
              <div className="flex gap-1 shrink-0">
                <button className="btn text-xs" onClick={() => doProbe(d.index)}>Probe</button>
                <button className="btn btn-primary text-xs"
                  onClick={() => connect({ name, source_type: d.is_bluetooth ? "bluetooth" : "webcam", index: d.index, start: true })}>
                  Connect &amp; Start
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "bluetooth" && (
        <div className="space-y-2">
          <button className="btn w-full" onClick={scanBt} disabled={busy}>Scan Bluetooth</button>
          {busy && !btDevs && <Spinner />}
          {btDevs && (
            <>
              <p className="text-[11px] text-cmd-warn leading-snug">{btDevs.note}</p>
              {btDevs.devices?.map((d: any, i: number) => (
                <div key={i} className="flex items-center justify-between border border-cmd-border rounded p-2">
                  <div className="text-sm text-white truncate">
                    {d.name}
                    {d.looks_like_camera && <span className="ml-1 text-[10px] text-cmd-ok">camera</span>}
                    {d.is_adapter && <span className="ml-1 text-[10px] text-cmd-muted">adapter</span>}
                  </div>
                </div>
              ))}
              <div className="border-t border-cmd-border pt-2 space-y-2">
                <p className="text-[11px] text-cmd-muted">A paired Bluetooth camera appears as a video device. Enter its index:</p>
                <div className="flex gap-2">
                  <input className="input w-20" type="number" min={0} value={index}
                    onChange={(e) => setIndex(Number(e.target.value))} />
                  <button className="btn text-xs" onClick={() => doProbe(index)}>Probe</button>
                  <button className="btn btn-primary text-xs flex-1"
                    onClick={() => connect({ name, source_type: "bluetooth", index, start: true })}>
                    Connect &amp; Start
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {tab === "ip" && (
        <div className="space-y-2">
          <p className="text-[11px] text-cmd-muted leading-snug">
            Turn a phone into a camera with an IP-webcam app, then paste its stream URL
            (e.g. <span className="font-mono">rtsp://192.168.1.9:8080/h264</span> or
            <span className="font-mono"> http://192.168.1.9:8080/video</span>).
          </p>
          <input className="input w-full font-mono text-xs" placeholder="rtsp:// or http:// stream URL"
            value={url} onChange={(e) => setUrl(e.target.value)} />
          <button className="btn btn-primary w-full" disabled={busy || !url}
            onClick={() => connect({ name, source_type: "rtsp", url, start: true })}>
            Connect &amp; Start
          </button>
        </div>
      )}

      {msg && <div className="text-xs text-cmd-accent">{msg}</div>}
    </div>
  );
}
