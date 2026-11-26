/* Applies the saved light/dark choice before first paint (kept tiny, loaded in <head>). */
try { var t = localStorage.getItem("osf-theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) {}
