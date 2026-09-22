/* Ayudas de la interfaz web (plan.md DT-08).
 *
 * Son solo una comodidad: el servidor vuelve a validarlo todo y la aplicación
 * funciona igual sin este fichero.
 */
(function () {
  "use strict";

  var LETRAS = "TRWAGMYFPDXBNJZSQVHLCKE";
  var NIE = { X: "0", Y: "1", Z: "2" };

  function normalizar(texto) {
    return (texto || "").replace(/[\s\-.]/g, "").toUpperCase();
  }

  /* Letra de control de un DNI o NIE (RN-04, RN-05). */
  function letraEsperada(doc) {
    if (/^\d{8}[A-Z]$/.test(doc)) return LETRAS[parseInt(doc.slice(0, 8), 10) % 23];
    if (/^[XYZ]\d{7}[A-Z]$/.test(doc)) return LETRAS[parseInt(NIE[doc[0]] + doc.slice(1, 8), 10) % 23];
    return null;
  }

  function mensajeLetra(doc) {
    var esperada = letraEsperada(doc);
    if (!esperada) return "";
    return doc.slice(-1) === esperada
      ? '<span class="pista-ok">✓ letra de control correcta</span>'
      : '<span class="pista-mal">✗ la letra debería ser ' + esperada + "</span>";
  }

  /* Misma deducción que identity.detectar_criterio_busqueda. */
  function detectar(texto) {
    var limpio = (texto || "").trim();
    if (!limpio) return null;
    if (/^HC-\d{4}-\d{6}$/i.test(limpio)) return { tipo: "código de historia clínica" };
    var doc = normalizar(limpio);
    if (/^\d{8}[A-Z]$/.test(doc)) return { tipo: "DNI", doc: doc };
    if (/^[XYZ]\d{7}[A-Z]$/.test(doc)) return { tipo: "NIE", doc: doc };
    if (/\d/.test(doc) && /^[A-Z0-9]{5,20}$/.test(doc)) return { tipo: "pasaporte" };
    return { tipo: null };
  }

  /* ---- Buscador ---------------------------------------------------------- */
  var buscador = document.getElementById("buscador");
  var pista = document.getElementById("pista");
  if (buscador && pista) {
    var ejemplos = pista.innerHTML;

    var enlazarEjemplos = function () {
      pista.querySelectorAll("[data-rellenar]").forEach(function (b) {
        b.addEventListener("click", function () {
          buscador.value = b.getAttribute("data-rellenar");
          buscador.form.submit();
        });
      });
    };

    var actualizar = function () {
      var d = detectar(buscador.value);
      if (!d) { pista.innerHTML = ejemplos; enlazarEjemplos(); return; }
      if (!d.tipo) {
        pista.innerHTML = '<span class="pista-mal">No parece un documento ni un código de historia clínica</span>';
        return;
      }
      pista.innerHTML = 'Se buscará por <span class="pista-tipo">' + d.tipo + "</span> " + (d.doc ? mensajeLetra(d.doc) : "");
    };

    enlazarEjemplos();
    buscador.addEventListener("input", actualizar);
    if (buscador.value) actualizar();
  }

  /* ---- Documento en el formulario ---------------------------------------- */
  var tipo = document.getElementById("tipo_documento");
  var numero = document.getElementById("numero_documento");
  var verificador = document.getElementById("verificador-documento");
  if (tipo && numero && verificador) {
    var comprobar = function () {
      var doc = normalizar(numero.value);
      if (!doc) { verificador.innerHTML = ""; return; }
      if (tipo.value === "PASAPORTE") {
        verificador.innerHTML = /^[A-Z0-9]{5,20}$/.test(doc)
          ? '<span class="pista-ok">✓ formato de pasaporte válido</span>'
          : '<span class="pista-mal">✗ entre 5 y 20 letras o números</span>';
        return;
      }
      var patron = tipo.value === "DNI" ? /^\d{8}[A-Z]$/ : /^[XYZ]\d{7}[A-Z]$/;
      verificador.innerHTML = patron.test(doc)
        ? mensajeLetra(doc)
        : '<span class="suave">' + (tipo.value === "DNI" ? "8 dígitos y una letra" : "X, Y o Z + 7 dígitos + letra") + "</span>";
    };
    numero.addEventListener("input", comprobar);
    tipo.addEventListener("change", comprobar);
    comprobar();
  }

  /* ---- Copiar patient_id -------------------------------------------------- */
  document.querySelectorAll("[data-copiar]").forEach(function (boton) {
    boton.addEventListener("click", function () {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(boton.getAttribute("data-copiar")).then(function () {
        boton.textContent = "Copiado ✓";
        setTimeout(function () { boton.textContent = "Copiar"; }, 1600);
      });
    });
  });
})();
