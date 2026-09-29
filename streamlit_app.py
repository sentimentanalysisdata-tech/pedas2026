"""
PeDaS 2026 - Dashboard analitik DNS

Dashboard ini membaca tabel ringkasan di folder dashboard_data/ yang dihasilkan oleh analisis_dns.py
dari SELURUH 11.712.623 pesan DNS (bukan sampel), sehingga angkanya identik dengan laporan.
Data mentah dan IP resolver tidak dimuat; nama domain disamarkan (D1-D14).
Jalankan: streamlit run dashboard.py
"""
import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_V = tuple(int(x) for x in st.__version__.split(".")[:2])
LEBAR = {"width": "stretch"} if _V >= (1, 50) else {"use_container_width": True}  # kompatibel Streamlit lama & baru

st.set_page_config(page_title="Analitik DNS .id - PeDaS 2026", page_icon="📊", layout="wide")

_BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(_BASE, "dashboard_data")
if not os.path.isdir(DATA):  # tabel juga boleh diletakkan langsung di folder utama
    DATA = _BASE
BLUE, ORANGE, GREY, INK2 = "#2a78d6", "#eb6834", "#8a8984", "#52514e"
SRC = "Sumber: data DNS PeDaS 2026, 19 Agu 2026 14.49–15.19 WIB; olahan tim."


def fmt(x, d=0):
    return f"{x:,.{d}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def pct(a, b, d=1):
    return fmt(100 * a / b, d) + "%"


@st.cache_data
def muat():
    S = json.load(open(os.path.join(DATA, "ringkasan.json")))
    t = {n: pd.read_csv(os.path.join(DATA, f"{n}.csv")) for n in
         ["per_menit", "rtype_do", "jenis_respons", "rcode", "qtype_query", "komposisi_pesan", "delegasi_tersamar"]}
    t["per_menit"]["mnt"] = pd.to_datetime(t["per_menit"]["mnt"], utc=True).dt.tz_convert("Asia/Jakarta")
    return S, t


S, T = muat()
q, qm, udp = S["queries"], S["query_tercocok"], S["respons_udp_tercocok"]


def gaya(fig, h=360):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(size=13),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
    return fig


# ------------------------------------------------------------------ header
st.title("Beban tersembunyi di server otoritatif .id")
st.caption(f"{fmt(S['records'])} pesan DNS (seluruh data, bukan sampel) · 19 Agustus 2026, "
           "14.49.57–15.19.57 WIB · Pengguna hasil: tim operasi DNS registri .id")

k = st.columns(5)
k[0].metric("Query (qr=0)", fmt(q), help="Volume permintaan hanya dari query; respons tidak dijumlahkan.")
k[1].metric("Query terjawab", pct(qm, q, 2), help="Query yang berhasil dipasangkan dengan responsnya.")
k[2].metric("Beban dari tanya-ulang", pct(S["hot_query"], qm), help="Query untuk 14 delegasi yang ditanya ulang (Temuan 1).")
k[3].metric("Respons UDP terpotong", pct(S["udp_terpotong"], udp, 2), help="TC=1 / seluruh respons UDP terpasangkan (Temuan 2).")
nx_n = T["jenis_respons"].set_index("rtype").loc["NXDOMAIN", "n"]
k[4].metric("NXDOMAIN (dari respons)", pct(nx_n, T["jenis_respons"].n.sum(), 1), help="Penyebut: respons terpasangkan (Temuan 3).")

tabs = st.tabs(["Ringkasan data", "Temuan 1 · Tanya-ulang", "Temuan 2 · Pemotongan", "Temuan 3 · NXDOMAIN per menit",
                "Rekomendasi", "Definisi & metode"])

# ------------------------------------------------------------------ ringkasan
with tabs[0]:
    st.markdown(f"Layanan sehat: **{pct(qm, q, 2)}** query terjawab dengan median waktu proses "
                f"**{fmt(S['latensi_p50_ms'], 2)} ms** (p99 {fmt(S['latensi_p99_ms'], 2)} ms); rata-rata "
                f"**{fmt(S['qps_rata'])} query/detik** (maksimum {fmt(S['qps_maks'])}). "
                "Masalahnya adalah **efisiensi**: bagian beban yang sebenarnya tidak perlu.")
    c1, c2 = st.columns(2)
    jr = T["jenis_respons"].sort_values("n")
    f = go.Figure(go.Bar(x=jr.pct, y=jr.rtype, orientation="h", marker_color=BLUE,
                         text=[fmt(v, 2) + "%" for v in jr.pct], textposition="outside",
                         hovertemplate="%{y}: %{x:.2f}% dari respons<extra></extra>"))
    f.update_xaxes(title="% dari respons terpasangkan", range=[0, 95])
    c1.subheader("Jenis respons")
    c1.plotly_chart(gaya(f, 300), **LEBAR)
    qt = T["qtype_query"].dropna().head(8).sort_values("n")
    f = go.Figure(go.Bar(x=qt.pct, y=qt.qtype_name, orientation="h", marker_color=BLUE,
                         text=[fmt(v, 1) + "%" for v in qt.pct], textposition="outside",
                         hovertemplate="%{y}: %{x:.2f}% dari query<extra></extra>"))
    f.update_xaxes(title="% dari query", range=[0, 58])
    c2.subheader("Tipe query teratas")
    c2.plotly_chart(gaya(f, 300), **LEBAR)
    st.caption("Porsi NS yang besar konsisten dengan QNAME minimisation (RFC 9156). " + SRC)

# ------------------------------------------------------------------ temuan 1
with tabs[1]:
    d = T["delegasi_tersamar"]
    st.markdown(f"**Satu jaringan resolver (165 IP dalam satu /48) mengirim {pct(S['jaringan_A_query'], qm)} seluruh query; "
                f"{pct(S['jaringan_A_query_ke_hot'], S['jaringan_A_query'])} di antaranya hanya untuk 14 delegasi.** "
                f"Totalnya {fmt(S['hot_query'])} query ({pct(S['hot_query'], qm)} beban, ≈{fmt(S['hot_query'] / 1800)} query/detik). "
                f"Resolver lain menanyakan domain yang sama hanya 1–8 kali, dan jaringan A bersikap normal pada domain lain "
                f"({fmt(S['jaringan_A_qpr_domain_lain'], 2)} query per IP per domain; median pembanding {fmt(S['median_qpr_pembanding'], 1)}).")
    urut = list(dict.fromkeys(d.kode))
    f = go.Figure()
    for kel, col in [("Jaringan resolver A", BLUE), ("Resolver lain", ORANGE)]:
        s = d[d.kelompok == kel].set_index("kode").reindex(urut)
        f.add_bar(y=urut, x=s.query_per_ip, name=kel, orientation="h", marker_color=col,
                  customdata=s[["query", "ip_resolver"]].values,
                  hovertemplate="%{y} · " + kel + "<br>%{x:,.1f} query per IP<br>%{customdata[0]:,} query dari %{customdata[1]} IP<extra></extra>")
    f.add_vline(x=S["median_qpr_pembanding"], line_dash="dash", line_color=GREY,
                annotation_text="median domain lain ≈ 1,3", annotation_position="bottom right")
    f.update_layout(barmode="group")
    f.update_xaxes(type="log", title="Query per IP resolver per domain dalam 30 menit (skala log)")
    f.update_yaxes(autorange="reversed")
    st.plotly_chart(gaya(f, 560), **LEBAR)
    st.caption("Nama domain disamarkan (D1–D14, hanya sufiks ditampilkan); IP resolver tidak dipublikasikan. "
               "Kriteria: ≥50 query per IP dan ditanya ≥100 resolver. " + SRC)
    with st.expander("Tabel data"):
        st.dataframe(d.style.format({"query": "{:,.0f}", "query_per_ip": "{:,.1f}"}), **LEBAR, hide_index=True)

# ------------------------------------------------------------------ temuan 2
with tabs[2]:
    r = T["rtype_do"]
    st.markdown(f"**{fmt(S['udp_terpotong'])} dari {fmt(udp)} respons UDP ({pct(S['udp_terpotong'], udp, 2)}) terpotong (TC=1); "
                f"{pct(S['udp_terpotong_negatif'], S['udp_terpotong'])} adalah respons negatif DNSSEC (NXDOMAIN/NODATA).** "
                f"{pct(S['tc_diikuti_tcp'], S['udp_terpotong'])} diulang lewat TCP dari IP yang sama "
                f"(median {fmt(S['tc_ke_tcp_median_ms'], 1)} ms); TCP kini {pct(S['query_tcp'], q, 2)} query.")
    order = ["Referral (delegasi)", "NODATA", "NXDOMAIN"]
    c1, c2 = st.columns(2)
    f = go.Figure()
    for do, name, col in [(0, "DO=0", ORANGE), (1, "DO=1 (minta DNSSEC)", BLUE)]:
        s = r[r.do_ == do].set_index("rtype").reindex(order)
        v = 100 * s.tc / s.udp
        f.add_bar(x=order, y=v, name=name, marker_color=col, text=[fmt(x, 1) + "%" for x in v], textposition="outside",
                  customdata=s[["tc", "udp"]].values,
                  hovertemplate="%{x} · " + name + "<br>%{y:.2f}% terpotong<br>%{customdata[0]:,.0f} dari %{customdata[1]:,.0f}<extra></extra>")
    f.update_layout(barmode="group")
    f.update_yaxes(title="% respons UDP terpotong", range=[0, 58])
    c1.subheader("Tingkat pemotongan per jenis respons")
    c1.plotly_chart(gaya(f), **LEBAR)
    s = r[r.do_ == 1].set_index("rtype").reindex(order)
    f = go.Figure(go.Bar(x=order, y=s.tcp_len, marker_color=BLUE, text=[fmt(x) + " B" for x in s.tcp_len],
                         textposition="outside", hovertemplate="%{x}: median %{y:,.0f} byte<extra></extra>", name="DO=1"))
    f.add_hline(y=1232, line_color=ORANGE, line_width=2, annotation_text="batas UDP 1.232 B", annotation_position="top left")
    f.update_yaxes(title="Median ukuran penuh via TCP (byte)", range=[0, 2150])
    c2.subheader("Ukuran respons penuh (DO=1)")
    c2.plotly_chart(gaya(f), **LEBAR)
    st.caption("Kunci zona .id yang teramati memakai algoritme 8 (RSA/SHA-256). " + SRC)

# ------------------------------------------------------------------ temuan 3
with tabs[3]:
    m = T["per_menit"].iloc[1:].reset_index(drop=True)  # menit 14.49 hanya 3 detik
    base = m.pct_nx.iloc[17:].median()
    ambang = st.slider("Ambang peringatan % NXDOMAIN per menit (rekomendasi R3)", 10.0, 25.0, 15.0, 0.5, format="%.1f%%")
    lewat = m[m.pct_nx > ambang]
    st.markdown(f"Baseline 15.07–15.19: **{fmt(base, 1)}%**. Pada 15.01–15.04 NXDOMAIN naik dari "
                f"{fmt(S['nx_per_menit_baseline'])} menjadi {fmt(S['nx_per_menit_lonjakan'])} per menit (2,2×). "
                f"Dengan ambang **{fmt(ambang, 1)}%**, **{len(lewat)} menit** memicu peringatan"
                + (": " + ", ".join(t.strftime("%H.%M") for t in lewat.mnt) if len(lewat) else "") + ".")
    f = go.Figure()
    f.add_scatter(x=m.mnt, y=m.pct_nx, name="% NXDOMAIN dari respons", mode="lines+markers", line=dict(color=BLUE, width=2),
                  customdata=m[["nx", "q"]].values,
                  hovertemplate="%{x|%H.%M} WIB<br>NXDOMAIN %{y:.2f}%<br>%{customdata[0]:,.0f} dari %{customdata[1]:,.0f} respons<extra></extra>")
    f.add_scatter(x=m.mnt, y=m.pct_tc, name="% respons UDP terpotong", mode="lines+markers", line=dict(color=ORANGE, width=2),
                  hovertemplate="%{x|%H.%M} WIB<br>terpotong %{y:.2f}%<extra></extra>")
    f.add_hline(y=ambang, line_dash="dash", line_color=GREY, annotation_text=f"ambang {fmt(ambang, 1)}%",
                annotation_position="top left")
    if len(lewat):
        f.add_scatter(x=lewat.mnt, y=lewat.pct_nx, mode="markers", name="melewati ambang",
                      marker=dict(size=13, color="rgba(0,0,0,0)", line=dict(color="#e34948", width=2)), hoverinfo="skip")
    f.update_xaxes(tickformat="%H.%M", title="Waktu (WIB)")
    f.update_yaxes(title="Persen", range=[0, 26])
    st.plotly_chart(gaya(f, 400), **LEBAR)
    st.caption(f"Dua klien menyumbang {fmt(S['nx_lonjakan_kontribusi_2_klien'])} NXDOMAIN per menit saat lonjakan; sisanya tersebar pada "
               f"{fmt(S['nx_lonjakan_nama_unik'])} nama dari {fmt(S['nx_lonjakan_klien'])} klien. Ini anomali volume, "
               "bukan bukti serangan atau phishing. " + SRC)

# ------------------------------------------------------------------ rekomendasi
with tabs[4]:
    st.table(pd.DataFrame([
        ["R1", "Periksa 14 delegasi (NS induk vs anak, jawaban otoritatif, DS) dan kirim bukti pola ke operator jaringan resolver A serta registrar terkait.",
         "NOC registri; layanan registrar", "Query per IP per domain untuk D1–D14 <10 per 30 menit; beban turun hingga ±35% (≈1.100 query/detik)."],
        ["R2", "Uji di lab ukuran NXDOMAIN/NODATA bertanda tangan untuk rollover algoritme zona .id dari RSA/SHA-256 (8) ke ECDSA P-256 (13) sesuai RFC 8624.",
         "Tim DNSSEC registri", "NXDOMAIN DO=1 <1.232 B; pemotongan respons negatif <5%; query TCP <1%."],
        ["R3", "Pantau % NXDOMAIN per menit (peringatan >15%) dan resolver dengan >1.000 NXDOMAIN/menit yang biasanya <10; tindak lanjut berupa investigasi, bukan blokir otomatis.",
         "NOC/SOC registri", "Lonjakan seperti 15.01–15.04 terdeteksi <2 menit; setiap peringatan tercatat hasilnya."],
    ], columns=["Kode", "Tindakan", "Pelaksana", "Indikator keberhasilan"]).set_index("Kode"))
    st.caption("Prioritas: R1 (dampak terbesar, biaya rendah, tanpa mengubah konfigurasi zona) → R2 → R3.")

# ------------------------------------------------------------------ definisi
with tabs[5]:
    st.markdown("""
- **Unit analisis:** satu pesan DNS. Volume permintaan dihitung hanya dari query (qr=0); query dan respons tidak dijumlahkan.
- **Pencocokan query–respons:** respons pertama sesudah query dengan protokol, IP & port klien, IP server, dns_id, qname persis
  (termasuk kapitalisasi 0x20) dan qtype yang sama. dns_id saja tidak dipakai sebagai kunci.
- **Penyebut:** jenis respons & rcode → respons terpasangkan; tingkat pemotongan → respons UDP terpasangkan.
- **Tanya-ulang:** query per IP resolver per domain terdaftar dalam 30 menit; pembanding = median domain yang ditanya ≥100 resolver.
- **Waktu:** ts_iso berzona UTC, ditampilkan dalam WIB (UTC+7).
- **Etika:** IP adalah resolver, bukan orang; IP tidak ditampilkan dan nama domain disamarkan. Anomali tidak dinyatakan sebagai serangan.
""")
    st.subheader("Komposisi pesan")
    st.dataframe(T["komposisi_pesan"], **LEBAR, hide_index=True)
    st.caption("Seluruh tabel di dashboard ini dihasilkan oleh analisis_dns.py dari data lengkap; tidak ada data mentah yang dimuat.")
