/* Dashboard Overview: mengambil /api/ringkasan lalu menggambar kartu, grafik Plotly, dan tabel.
   Filter periode/pembanding/ukuran/ambang dikirim ke server (divalidasi daftar putih di Django);
   filter arah/cari/urutan dikerjakan di browser pada data yang sudah diterima.
   Nama komoditas berasal dari data, jadi selalu dimasukkan lewat textContent (bukan innerHTML). */
(function () {
    "use strict";

    var API = document.currentScript.dataset.api;
    var COMPARE = document.currentScript.dataset.compare || ""; // halaman Perbandingan Wilayah (opsional)
    var BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
    var FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif';
    var ARAH = ["semua", "naik", "turun", "tetap"];
    var URUT = ["perubahan_desc", "perubahan_asc", "harga_desc", "nama"];
    var BAWAAN = { arah: "semua", urut: "perubahan_desc", cari: "", ukuran: "median" };

    var state = {
        ukuran: BAWAAN.ukuran, periode: null, pembandingPilihan: "", ambang: null,
        arah: BAWAAN.arah, urut: BAWAAN.urut, cari: BAWAAN.cari,
        komoditasTren: null, data: null, req: 0
    };

    function $(id) { return document.getElementById(id); }

    // ---------- format ----------
    function rupiah(n) { return "Rp " + Math.round(n).toLocaleString("id-ID"); }
    function persen(n) {
        var s = n > 0 ? "+" : n < 0 ? "−" : "";
        return s + Math.abs(n).toLocaleString("id-ID", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
    }
    function labelPeriode(p) { return BULAN[parseInt(p.slice(5), 10) - 1] + " " + p.slice(0, 4); }
    function judul(s) { return s.toLowerCase().replace(/(^|[\s/])(\p{L})/gu, function (m, a, b) { return a + b.toUpperCase(); }); }
    function pendek(s, maks) { maks = maks || 24; return s.length > maks ? s.slice(0, maks - 1) + "…" : s; }
    function tanggalId(iso) {
        var d = new Date(iso + "T00:00:00");
        return d.getDate() + " " + BULAN[d.getMonth()] + " " + d.getFullYear();
    }

    function warna() {
        var css = getComputedStyle(document.documentElement);
        function v(n) { return css.getPropertyValue(n).trim(); }
        return {
            naik: v("--naik"), turun: v("--turun"), seri: v("--seri"), ink: v("--ink"), ink2: v("--ink2"),
            muted: v("--muted"), grid: v("--grid"), axis: v("--axis"), surface: v("--surface")
        };
    }

    function el(tag, text, cls) {
        var e = document.createElement(tag);
        if (text !== undefined && text !== null) e.textContent = text;
        if (cls) e.className = cls;
        return e;
    }

    // ---------- URL (bisa dibagikan) ----------
    function bacaUrl() {
        var q = new URLSearchParams(location.search);
        var per = /^\d{4}-\d{2}$/;
        if (per.test(q.get("periode") || "")) state.periode = q.get("periode");
        if (per.test(q.get("pembanding") || "")) state.pembandingPilihan = q.get("pembanding");
        if (q.get("ukuran") === "rata_rata") state.ukuran = "rata_rata";
        if (/^\d{1,2}$/.test(q.get("ambang") || "")) state.ambang = q.get("ambang");
        if (ARAH.indexOf(q.get("arah")) !== -1) state.arah = q.get("arah");
        if (URUT.indexOf(q.get("urut")) !== -1) state.urut = q.get("urut");
        if (q.get("cari")) state.cari = q.get("cari").slice(0, 40);
    }

    function tulisUrl() {
        var q = new URLSearchParams();
        if (state.periode) q.set("periode", state.periode);
        if (state.pembandingPilihan) q.set("pembanding", state.pembandingPilihan);
        if (state.ukuran !== BAWAAN.ukuran) q.set("ukuran", state.ukuran);
        if (state.ambang) q.set("ambang", state.ambang);
        if (state.arah !== BAWAAN.arah) q.set("arah", state.arah);
        if (state.urut !== BAWAAN.urut) q.set("urut", state.urut);
        if (state.cari) q.set("cari", state.cari);
        var qs = q.toString();
        try { history.replaceState(null, "", qs ? "?" + qs : location.pathname); } catch (e) { /* abaikan */ }
    }

    // ---------- pengambilan data ----------
    function muat() {
        var id = ++state.req;
        var q = new URLSearchParams({ ukuran: state.ukuran });
        if (state.periode) q.set("periode", state.periode);
        if (state.pembandingPilihan) q.set("pembanding", state.pembandingPilihan);
        if (state.ambang) q.set("ambang", state.ambang);
        fetch(API + "?" + q.toString(), { headers: { Accept: "application/json" } })
            .then(function (r) {
                return r.json().then(function (body) {
                    if (!r.ok) throw new Error(body.error || "Gagal memuat data (HTTP " + r.status + ")");
                    return body;
                });
            })
            .then(function (data) {
                if (id !== state.req) return; // respons lama diabaikan
                state.data = data;
                state.periode = data.periode;
                tampilkan(data);
            })
            .catch(function (err) {
                if (id !== state.req) return;
                pesan(err.message || "Tidak dapat memuat data. Pastikan Django dan MongoDB berjalan.");
            });
    }

    function pesan(teks) {
        var box = $("pesan");
        box.replaceChildren();
        var list = [].concat(teks || []);
        list.forEach(function (t) { box.appendChild(el("p", "ⓘ " + t)); });
        box.hidden = list.length === 0;
    }

    // ---------- filter di browser ----------
    function daftarTampil(d) {
        var q = state.cari.trim().toLowerCase();
        var rows = d.komoditas.filter(function (k) {
            if (q && k.nama.toLowerCase().indexOf(q) === -1) return false;
            var p = k.perubahan_pct;
            if (state.arah === "naik") return p !== null && p > 0;
            if (state.arah === "turun") return p !== null && p < 0;
            if (state.arah === "tetap") return p !== null && p === 0;
            return true;
        });
        function p(k, kosong) { return k.perubahan_pct === null ? kosong : k.perubahan_pct; }
        rows.sort(function (a, b) {
            if (state.urut === "perubahan_asc") return p(a, Infinity) - p(b, Infinity);
            if (state.urut === "harga_desc") return b.nilai - a.nilai;
            if (state.urut === "nama") return a.nama.localeCompare(b.nama, "id");
            return p(b, -Infinity) - p(a, -Infinity) || a.nama.localeCompare(b.nama, "id");
        });
        return rows;
    }

    // ---------- render ----------
    function tampilkan(d) {
        isiPeriode(d);
        isiPembanding(d);
        isiAmbang(d);
        $("u-median").setAttribute("aria-pressed", String(d.ukuran === "median"));
        $("u-rata_rata").setAttribute("aria-pressed", String(d.ukuran === "rata_rata"));
        $("subjudul").textContent = labelPeriode(d.periode) +
            (d.pembanding ? " dibandingkan " + labelPeriode(d.pembanding) : " (tanpa periode pembanding)") +
            " · harga " + (d.ukuran === "median" ? "median" : "rata-rata");
        pesan(d.catatan);
        renderKpi(d);
        renderPeringkat(d);
        isiPilihanKomoditas(d);
        renderFilter();
        renderGrafik();
        tulisUrl();
    }

    // Bagian yang bergantung pada filter arah/cari/urutan.
    function renderFilter() {
        var d = state.data;
        if (!d) return;
        var rows = daftarTampil(d);
        $("hitung").textContent = "Menampilkan " + rows.length + " dari " + d.komoditas.length + " komoditas.";
        [].forEach.call(document.querySelectorAll("[data-arah]"), function (b) {
            b.setAttribute("aria-pressed", String(b.dataset.arah === state.arah));
        });
        $("urut").value = state.urut;
        renderTabel(d, rows);
    }

    function isiPeriode(d) {
        var sel = $("periode");
        sel.replaceChildren();
        d.periode_tersedia.slice().reverse().forEach(function (p) {
            var o = el("option", labelPeriode(p.periode) + (p.lengkap ? "" : " (belum lengkap)"));
            o.value = p.periode;
            sel.appendChild(o);
        });
        sel.value = d.periode;
    }

    function isiPembanding(d) {
        var sel = $("pembanding");
        sel.replaceChildren();
        var auto = el("option", "Bulan sebelumnya");
        auto.value = "";
        sel.appendChild(auto);
        d.periode_tersedia.slice().reverse().forEach(function (p) {
            if (p.periode === d.periode) return;
            var o = el("option", labelPeriode(p.periode) + (p.lengkap ? "" : " (belum lengkap)"));
            o.value = p.periode;
            sel.appendChild(o);
        });
        sel.value = state.pembandingPilihan;
        if (sel.value !== state.pembandingPilihan) { state.pembandingPilihan = ""; sel.value = ""; }
    }

    function isiAmbang(d) {
        var sel = $("ambang");
        sel.replaceChildren();
        d.ambang_pilihan.forEach(function (a) {
            var o = el("option", a + "%");
            o.value = String(a);
            sel.appendChild(o);
        });
        sel.value = String(d.ambang_lonjakan);
    }

    function renderKpi(d) {
        var k = d.kpi, s = d.status;
        $("kpi-jumlah").textContent = k.jumlah_komoditas;
        $("kpi-jumlah-sub").textContent = d.pembanding ? "vs " + labelPeriode(d.pembanding) : "";
        if (k.naik_terbesar) {
            $("kpi-naik-nilai").textContent = persen(k.naik_terbesar.perubahan_pct);
            $("kpi-naik-nama").textContent = judul(k.naik_terbesar.nama);
        } else {
            $("kpi-naik-nilai").textContent = "–";
            $("kpi-naik-nama").textContent = "Tidak ada kenaikan";
        }
        if (k.turun_terbesar) {
            $("kpi-turun-nilai").textContent = persen(k.turun_terbesar.perubahan_pct);
            $("kpi-turun-nama").textContent = judul(k.turun_terbesar.nama);
        } else {
            $("kpi-turun-nilai").textContent = "–";
            $("kpi-turun-nama").textContent = "Tidak ada penurunan";
        }
        $("kpi-data").textContent = s.data_terakhir ? tanggalId(s.data_terakhir) : "–";
        $("kpi-data-sub").textContent = s.total_dokumen.toLocaleString("id-ID") + " data · " +
            s.baris_ditolak.toLocaleString("id-ID") + " ditolak saat ETL";
        $("lonjakan").textContent = k.lonjakan.length
            ? "Lonjakan (naik ≥ " + d.ambang_lonjakan + "%): " + k.lonjakan.map(function (x) { return judul(x.nama) + " " + persen(x.perubahan_pct); }).join(", ")
            : "Tidak ada komoditas yang naik ≥ " + d.ambang_lonjakan + "%.";
    }

    function isiRank(id, rows) {
        var ol = $(id);
        ol.replaceChildren();
        rows.forEach(function (k, i) {
            var li = document.createElement("li");
            var kiri = el("span");
            kiri.appendChild(el("span", i + 1, "n num"));
            kiri.appendChild(document.createTextNode(judul(k.nama)));
            li.appendChild(kiri);
            li.appendChild(el("span", rupiah(k.nilai), "num"));
            ol.appendChild(li);
        });
    }

    function renderPeringkat(d) {
        $("peringkat-sub").textContent = "Harga " + (d.ukuran === "median" ? "median" : "rata-rata") + " " + labelPeriode(d.periode);
        isiRank("tertinggi", d.kpi.tertinggi);
        isiRank("terendah", d.kpi.terendah);
    }

    function renderTabel(d, rows) {
        $("th-sekarang").textContent = labelPeriode(d.periode);
        $("th-pembanding").textContent = d.pembanding ? labelPeriode(d.pembanding) : "Pembanding";
        var tbody = document.querySelector("#tabel tbody");
        tbody.replaceChildren();
        if (!rows.length) {
            var tr0 = document.createElement("tr");
            var td0 = el("td", "Tidak ada komoditas yang cocok dengan filter.");
            td0.colSpan = 6;
            tr0.appendChild(td0);
            tbody.appendChild(tr0);
            return;
        }
        rows.forEach(function (k) {
            var tr = document.createElement("tr");
            var tdNama = document.createElement("td");
            if (COMPARE) {
                var link = el("a", judul(k.nama));
                link.href = COMPARE + "?" + new URLSearchParams({ komoditas: k.nama, periode: d.periode }).toString();
                link.title = "Bandingkan harga antarwilayah";
                tdNama.appendChild(link);
            } else {
                tdNama.textContent = judul(k.nama);
            }
            tr.appendChild(tdNama);
            tr.appendChild(el("td", rupiah(k.nilai)));
            tr.appendChild(el("td", k.nilai_pembanding === null ? "–" : rupiah(k.nilai_pembanding)));
            tr.appendChild(el("td", k.perubahan_pct === null ? "–" : persen(k.perubahan_pct)));
            tr.appendChild(el("td", rupiah(k.minimum) + " – " + rupiah(k.maksimum)));
            tr.appendChild(el("td", k.n_wilayah.toLocaleString("id-ID")));
            tbody.appendChild(tr);
        });
    }

    function isiPilihanKomoditas(d) {
        var sel = $("pilih-komoditas");
        var nama = Object.keys(d.tren).sort();
        if (!state.komoditasTren || nama.indexOf(state.komoditasTren) === -1) {
            state.komoditasTren = d.kpi.naik_terbesar ? d.kpi.naik_terbesar.nama : nama[0];
        }
        sel.replaceChildren();
        nama.forEach(function (n) {
            var o = el("option", judul(n));
            o.value = n;
            sel.appendChild(o);
        });
        sel.value = state.komoditasTren;
    }

    // ---------- grafik ----------
    function dasarLayout(c) {
        return {
            paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
            font: { family: FONT, size: 12, color: c.ink2 },
            separators: ",.", hovermode: "closest",
            hoverlabel: { font: { family: FONT } }
        };
    }
    var CONFIG = { displayModeBar: false, responsive: true };

    function renderGrafik() {
        if (!state.data) return;
        var c = warna();
        renderPerubahan(state.data, c);
        renderTren(state.data, c);
    }

    function renderPerubahan(d, c) {
        var box = $("grafik-perubahan");
        var rows = daftarTampil(d).filter(function (k) { return k.perubahan_pct !== null; });
        if (!rows.length) {
            Plotly.purge(box);
            box.textContent = d.pembanding
                ? "Tidak ada komoditas yang cocok dengan filter."
                : "Belum ada periode pembanding untuk bulan ini.";
            return;
        }
        box.textContent = "";
        var nama = rows.map(function (k) { return judul(k.nama); });
        var x = rows.map(function (k) { return k.perubahan_pct; });
        var sempit = box.clientWidth < 560;
        // Ruang di kiri/kanan sumbu supaya angka di ujung batang (juga yang negatif) tidak menabrak nama komoditas.
        var lo = Math.min(0, Math.min.apply(null, x)), hi = Math.max(0, Math.max.apply(null, x));
        var pad = Math.max(3, (hi - lo) * (sempit ? 0.28 : 0.16));
        var layout = Object.assign(dasarLayout(c), {
            height: Math.max(150, rows.length * 30 + 60),
            margin: { l: sempit ? 118 : 190, r: 16, t: 8, b: 36 },
            bargap: 0.45,
            xaxis: { range: [lo < 0 ? lo - pad : -hi * 0.03, hi + pad], ticksuffix: "%", gridcolor: c.grid, gridwidth: 1, zeroline: true, zerolinecolor: c.axis, zerolinewidth: 1, tickfont: { color: c.muted }, fixedrange: true },
            yaxis: { type: "category", autorange: "reversed", tickvals: nama, ticktext: nama.map(function (s) { return pendek(s, sempit ? 16 : 24); }), tickfont: { color: c.ink2 }, ticklen: 0, showgrid: false, fixedrange: true },
            hovermode: "closest"
        });
        Plotly.react(box, [{
            type: "bar", orientation: "h", x: x, y: nama,
            marker: { color: x.map(function (v) { return v >= 0 ? c.naik : c.turun; }) },
            text: x.map(persen), textposition: "outside", cliponaxis: false, textfont: { color: c.ink2, size: 12 },
            customdata: rows.map(function (k) {
                return [rupiah(k.nilai_pembanding), rupiah(k.nilai), rupiah(k.minimum) + " – " + rupiah(k.maksimum)];
            }),
            hovertemplate: "<b>%{y}</b><br>%{customdata[0]} → %{customdata[1]}<br>Perubahan %{text}<br>Rentang antarwilayah %{customdata[2]}<extra></extra>"
        }], layout, CONFIG);
    }

    function renderTren(d, c) {
        var box = $("grafik-tren");
        var seri = d.tren[state.komoditasTren] || [];
        if (!seri.length) { Plotly.purge(box); box.textContent = "Tidak ada data tren."; return; }
        box.textContent = "";
        var x = seri.map(function (s) { return s.periode; });
        var y = seri.map(function (s) { return s.nilai; });
        var n = x.length;
        var tickIdx = x.map(function (_, i) { return i; }).filter(function (i) { return (n - 1 - i) % 3 === 0; });
        var sorot = [d.periode, d.pembanding].filter(function (p) { return p && x.indexOf(p) !== -1; });
        var layout = Object.assign(dasarLayout(c), {
            height: 320, margin: { l: box.clientWidth < 560 ? 72 : 80, r: 16, t: 8, b: 40 },
            xaxis: { type: "category", tickmode: "array", tickvals: tickIdx.map(function (i) { return x[i]; }), ticktext: tickIdx.map(function (i) { return labelPeriode(x[i]); }), tickfont: { color: c.muted }, showgrid: false, linecolor: c.axis, fixedrange: true },
            yaxis: { tickprefix: "Rp ", tickformat: ",.0f", gridcolor: c.grid, gridwidth: 1, zeroline: false, tickfont: { color: c.muted }, fixedrange: true },
            showlegend: false, hovermode: "x"
        });
        Plotly.react(box, [
            {
                type: "scatter", mode: "lines", x: x, y: y, line: { color: c.seri, width: 2 },
                customdata: x.map(labelPeriode),
                hovertemplate: "<b>Rp %{y:,.0f}</b><br>%{customdata}<extra></extra>"
            },
            {
                type: "scatter", mode: "markers", hoverinfo: "skip",
                x: sorot, y: sorot.map(function (p) { return y[x.indexOf(p)]; }),
                marker: { size: 9, color: c.seri, line: { color: c.surface, width: 2 } }
            }
        ], layout, CONFIG);
    }

    // ---------- interaksi ----------
    // Filter yang diproses server: ubah state lalu ambil ulang data.
    $("periode").addEventListener("change", function (e) { state.periode = e.target.value; state.pembandingPilihan = ""; muat(); });
    $("pembanding").addEventListener("change", function (e) { state.pembandingPilihan = e.target.value; muat(); });
    $("ambang").addEventListener("change", function (e) { state.ambang = e.target.value; muat(); });
    ["median", "rata_rata"].forEach(function (u) {
        $("u-" + u).addEventListener("click", function () {
            if (state.ukuran === u) return;
            state.ukuran = u;
            muat();
        });
    });

    // Filter yang diproses di browser: cukup gambar ulang bagian terkait.
    function filterBerubah() { renderFilter(); renderGrafik(); tulisUrl(); }
    $("cari").addEventListener("input", function (e) { state.cari = e.target.value.slice(0, 40); filterBerubah(); });
    $("urut").addEventListener("change", function (e) { state.urut = e.target.value; filterBerubah(); });
    [].forEach.call(document.querySelectorAll("[data-arah]"), function (b) {
        b.addEventListener("click", function () { state.arah = b.dataset.arah; filterBerubah(); });
    });
    $("reset").addEventListener("click", function () {
        var butuhMuat = state.pembandingPilihan !== "" || state.ambang !== null;
        state.arah = BAWAAN.arah; state.urut = BAWAAN.urut; state.cari = BAWAAN.cari;
        state.pembandingPilihan = ""; state.ambang = null;
        $("cari").value = "";
        if (butuhMuat) muat(); else filterBerubah();
    });

    $("pilih-komoditas").addEventListener("change", function (e) {
        state.komoditasTren = e.target.value;
        renderGrafik();
    });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderGrafik);

    bacaUrl();
    $("cari").value = state.cari;
    muat();
})();
