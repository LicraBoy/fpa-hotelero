"""Evaluador mínimo de las fórmulas que genera `exportar_variance_formulas`.

No hay Excel ni LibreOffice en esta máquina para recalcular el libro exportado; este evaluador
entiende justo lo que el exportador escribe (`+ - * /`, comparaciones, `&`, `SUMIFS`, `AVERAGEIFS`,
`IF`, referencias a celdas y rangos, también de otras hojas) y permite comprobar **cada celda**
contra el motor. Lo que no entiende, lo rechaza con un error: nunca adivina.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from openpyxl import Workbook
from openpyxl.utils import column_index_from_string

_TOKEN = re.compile(
    r"""\s*(?:
    (?P<num>\d+(?:\.\d+)?)
  | (?P<str>"[^"]*")
  | (?P<ref>(?:[A-Za-z_]+!)?\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)
  | (?P<fn>[A-Z]+)(?=\()
  | (?P<op>>=|<=|<>|[-+*/&=<>(),])
    )""",
    re.VERBOSE,
)
_REF = re.compile(
    r"^(?:(?P<hoja>[A-Za-z_]+)!)?\$?(?P<c1>[A-Z]+)\$?(?P<f1>\d+)(?::\$?(?P<c2>[A-Z]+)\$?(?P<f2>\d+))?$"
)


class FormulaNoSoportada(ValueError):
    pass


class Evaluador:
    def __init__(self, libro: Workbook) -> None:
        self.libro = libro
        self._memo: dict[tuple[str, int, int], Decimal] = {}
        self._en_curso: set[tuple[str, int, int]] = set()

    # --- celdas -----------------------------------------------------------------------------
    def valor(self, hoja: str, columna: int, fila: int) -> Any:
        """Valor crudo de la celda (fórmula evaluada, número, texto o None)."""
        celda = self.libro[hoja].cell(row=fila, column=columna)
        v = celda.value
        if isinstance(v, str) and v.startswith("=") and celda.data_type == "f":
            clave = (hoja, columna, fila)
            if clave in self._memo:
                return self._memo[clave]
            if clave in self._en_curso:
                raise FormulaNoSoportada(f"Referencia circular en {hoja}!{columna},{fila}")
            self._en_curso.add(clave)
            try:
                resultado = _Analizador(self, hoja, v[1:]).evaluar()
            finally:
                self._en_curso.discard(clave)
            self._memo[clave] = resultado
            return resultado
        if isinstance(v, bool):
            raise FormulaNoSoportada("booleano")
        if isinstance(v, (int, float, Decimal)):
            return Decimal(str(v))
        return v

    def numero(self, hoja: str, columna: int, fila: int) -> Decimal:
        v = self.valor(hoja, columna, fila)
        if v is None or v == "":
            return Decimal(0)
        if isinstance(v, Decimal):
            return v
        raise FormulaNoSoportada(f"{hoja}!{columna},{fila} no es un número: {v!r}")

    def rango(self, hoja: str, c1: int, f1: int, c2: int, f2: int) -> list[Any]:
        return [self.valor(hoja, c, f) for f in range(f1, f2 + 1) for c in range(c1, c2 + 1)]


def _coincide(valor: Any, criterio: Any) -> bool:
    if isinstance(criterio, Decimal):
        return isinstance(valor, Decimal) and valor == criterio
    texto = str(criterio)
    m = re.match(r"^(>=|<=|<>|>|<|=)(.*)$", texto)
    if m:
        op, resto = m.groups()
        if not isinstance(valor, Decimal):
            return False
        x = Decimal(resto)
        return {
            ">=": valor >= x,
            "<=": valor <= x,
            ">": valor > x,
            "<": valor < x,
            "=": valor == x,
            "<>": valor != x,
        }[op]
    if isinstance(valor, Decimal):
        return False
    return isinstance(valor, str) and valor.lower() == texto.lower()


class _Analizador:
    def __init__(self, ev: Evaluador, hoja: str, texto: str) -> None:
        self.ev, self.hoja = ev, hoja
        self.tokens: list[tuple[str, str]] = []
        pos = 0
        texto = texto.rstrip()
        while pos < len(texto):
            m = _TOKEN.match(texto, pos)
            if not m or m.end() == pos:
                raise FormulaNoSoportada(f"No entiendo «{texto[pos : pos + 20]}» en «{texto}»")
            tipo = m.lastgroup or ""
            self.tokens.append((tipo, m.group(tipo)))
            pos = m.end()
        self.i = 0

    # --- gramática --------------------------------------------------------------------------
    def evaluar(self) -> Decimal:
        valor = self._comparacion()
        if self.i != len(self.tokens):
            raise FormulaNoSoportada("sobran símbolos al final de la fórmula")
        if not isinstance(valor, Decimal):
            raise FormulaNoSoportada("la fórmula no devuelve un número")
        return valor

    def _ver(self) -> tuple[str, str] | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _op(self, *ops: str) -> str | None:
        t = self._ver()
        if t and t[0] == "op" and t[1] in ops:
            self.i += 1
            return t[1]
        return None

    def _comparacion(self) -> Any:
        izq = self._concat()
        op = self._op("=", "<>", "<=", ">=", "<", ">")
        if not op:
            return izq
        der = self._concat()
        return Decimal(1) if _comparar(izq, op, der) else Decimal(0)

    def _concat(self) -> Any:
        izq = self._suma()
        while self._op("&"):
            der = self._suma()
            izq = _texto(izq) + _texto(der)
        return izq

    def _suma(self) -> Any:
        izq = self._producto()
        while op := self._op("+", "-"):
            der = self._producto()
            izq = _num(izq) + _num(der) if op == "+" else _num(izq) - _num(der)
        return izq

    def _producto(self) -> Any:
        izq = self._unario()
        while op := self._op("*", "/"):
            der = self._unario()
            if op == "*":
                izq = _num(izq) * _num(der)
            else:
                if _num(der) == 0:
                    raise ZeroDivisionError("#DIV/0!")
                izq = _num(izq) / _num(der)
        return izq

    def _unario(self) -> Any:
        if self._op("-"):
            return -_num(self._unario())
        if self._op("+"):
            return self._unario()
        return self._primario()

    def _primario(self) -> Any:
        t = self._ver()
        if t is None:
            raise FormulaNoSoportada("fórmula incompleta")
        self.i += 1
        tipo, texto = t
        if tipo == "num":
            return Decimal(texto)
        if tipo == "str":
            return texto[1:-1]
        if tipo == "ref":
            return self._ref(texto)
        if tipo == "fn":
            return self._funcion(texto)
        if tipo == "op" and texto == "(":
            v = self._comparacion()
            if not self._op(")"):
                raise FormulaNoSoportada("falta )")
            return v
        raise FormulaNoSoportada(f"símbolo inesperado {texto!r}")

    def _ref(self, texto: str) -> Any:
        m = _REF.match(texto)
        if not m:
            raise FormulaNoSoportada(f"referencia no válida {texto!r}")
        hoja = m.group("hoja") or self.hoja
        c1, f1 = column_index_from_string(m.group("c1")), int(m.group("f1"))
        if m.group("c2"):
            c2, f2 = column_index_from_string(m.group("c2")), int(m.group("f2"))
            return ("rango", self.ev.rango(hoja, c1, f1, c2, f2))
        v = self.ev.valor(hoja, c1, f1)
        return Decimal(0) if v is None else v

    def _argumentos(self) -> list[Any]:
        if not self._op("("):
            raise FormulaNoSoportada("falta (")
        args = [self._argumento()]
        while self._op(","):
            args.append(self._argumento())
        if not self._op(")"):
            raise FormulaNoSoportada("falta )")
        return args

    def _argumento(self) -> Any:
        try:
            return self._comparacion()
        except ZeroDivisionError:
            return _Error()

    def _funcion(self, nombre: str) -> Any:
        args = self._argumentos()
        if nombre == "IF":
            return args[1] if _num(args[0]) != 0 else args[2]
        if nombre in ("SUMIFS", "AVERAGEIFS"):
            suma = _lista(args[0])
            pares = args[1:]
            coinciden = [
                all(_coincide(_lista(pares[k])[j], pares[k + 1]) for k in range(0, len(pares), 2))
                for j in range(len(suma))
            ]
            elegidos = [v for v, ok in zip(suma, coinciden, strict=True) if ok]
            numeros = [v for v in elegidos if isinstance(v, Decimal)]
            if nombre == "SUMIFS":
                return sum(numeros, Decimal(0))
            if not numeros:
                raise ZeroDivisionError("#DIV/0! (AVERAGEIFS sin datos)")
            return sum(numeros, Decimal(0)) / len(numeros)
        raise FormulaNoSoportada(f"función {nombre} no soportada")


def _lista(x: Any) -> list[Any]:
    if isinstance(x, tuple) and x and x[0] == "rango":
        return list(x[1])
    raise FormulaNoSoportada("se esperaba un rango")


class _Error:
    """Un argumento que dio #DIV/0!: solo falla si la función lo usa (como el IF de Excel)."""


def _num(x: Any) -> Decimal:
    if isinstance(x, _Error):
        raise ZeroDivisionError("#DIV/0!")
    if isinstance(x, Decimal):
        return x
    if x is None or x == "":
        return Decimal(0)
    raise FormulaNoSoportada(f"no es un número: {x!r}")


def _texto(x: Any) -> str:
    if isinstance(x, Decimal):
        return format(x.normalize(), "f")
    return str(x)


def _comparar(a: Any, op: str, b: Any) -> bool:
    a = _num(a) if not isinstance(a, str) else a
    b = _num(b) if not isinstance(b, str) else b
    return {
        "=": a == b,
        "<>": a != b,
        "<=": a <= b,
        ">=": a >= b,
        "<": a < b,
        ">": a > b,
    }[op]
