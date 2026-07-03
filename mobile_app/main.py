# -*- coding: utf-8 -*-
"""
СУПЕР-МЕГА-УЛЬТРА ПРИЛОЖЕНИЕ (мобильная версия на Kivy)
========================================================
Три вкладки:
  1. Калькулятор
  2. Ежедневник (задачи по дням, листаешь стрелками)
  3. Доходы / Расходы + круговая диаграмма
"""

import ast
import json
import operator
import os
from datetime import datetime, timedelta

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse
from kivy.uix.popup import Popup
from kivy.uix.label import Label


class SafeCalculator:
    _OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    @classmethod
    def eval(cls, expr):
        tree = ast.parse(expr, mode="eval")
        return cls._eval_node(tree.body)

    @classmethod
    def _eval_node(cls, node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Недопустимое значение")
        if isinstance(node, ast.BinOp) and type(node.op) in cls._OPS:
            return cls._OPS[type(node.op)](cls._eval_node(node.left), cls._eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in cls._OPS:
            return cls._OPS[type(node.op)](cls._eval_node(node.operand))
        raise ValueError("Недопустимое выражение")


def show_popup(title, message):
    Popup(
        title=title,
        content=Label(text=message),
        size_hint=(0.8, 0.4),
    ).open()


class Storage:
    def __init__(self, path):
        self.path = path
        self.data = {"tasks": {}, "transactions": []}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        self.data.setdefault("tasks", {})
        self.data.setdefault("transactions", [])

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)


STORAGE = None


class CalculatorScreen(BoxLayout):
    display_text = StringProperty("")

    def on_key(self, value):
        if value == "C":
            self.display_text = ""
        elif value == "⌫":
            self.display_text = self.display_text[:-1]
        elif value == "=":
            try:
                expr = self.display_text.replace("×", "*").replace("÷", "/")
                result = SafeCalculator.eval(expr)
                self.display_text = str(result)
            except Exception:
                show_popup("Ошибка", "Некорректное выражение")
        else:
            self.display_text += value


class TaskRow(BoxLayout):
    text = StringProperty("")
    done = False
    index = NumericProperty(0)


class PlannerScreen(BoxLayout):
    current_date = StringProperty(datetime.now().strftime("%Y-%m-%d"))
    rows = ListProperty([])

    def on_kv_post(self, base_widget):
        self.refresh()

    def shift_day(self, delta):
        d = datetime.strptime(self.current_date, "%Y-%m-%d") + timedelta(days=delta)
        self.current_date = d.strftime("%Y-%m-%d")
        self.refresh()

    def go_today(self):
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self.refresh()

    def _tasks(self):
        return STORAGE.data["tasks"].setdefault(self.current_date, [])

    def add_task(self, text):
        text = text.strip()
        if not text:
            return
        self._tasks().append({"text": text, "done": False})
        STORAGE.save()
        self.refresh()
        self.ids.new_task_input.text = ""

    def toggle_task(self, index):
        tasks = self._tasks()
        tasks[index]["done"] = not tasks[index]["done"]
        STORAGE.save()
        self.refresh()

    def delete_task(self, index):
        tasks = self._tasks()
        del tasks[index]
        STORAGE.save()
        self.refresh()

    def refresh(self):
        container = self.ids.task_list
        container.clear_widgets()
        for i, t in enumerate(self._tasks()):
            row = TaskRow()
            prefix = "[x] " if t["done"] else "[ ] "
            row.text = prefix + t["text"]
            row.index = i
            row.ids.check_btn.bind(on_release=lambda w, idx=i: self.toggle_task(idx))
            row.ids.del_btn.bind(on_release=lambda w, idx=i: self.delete_task(idx))
            container.add_widget(row)


PALETTE = [
    (0.90, 0.30, 0.30, 1), (0.30, 0.55, 0.90, 1), (0.35, 0.80, 0.45, 1),
    (0.95, 0.70, 0.20, 1), (0.60, 0.35, 0.85, 1), (0.20, 0.75, 0.75, 1),
    (0.85, 0.45, 0.65, 1), (0.55, 0.55, 0.55, 1),
]


class PieChart(Widget):
    slices = ListProperty([])

    def on_slices(self, *args):
        self.redraw()

    def on_size(self, *args):
        self.redraw()

    def redraw(self):
        self.canvas.clear()
        total = sum(v for _, v in self.slices)
        if total <= 0:
            return
        size = min(self.width, self.height) * 0.9
        cx = self.center_x
        cy = self.center_y
        with self.canvas:
            start = 0.0
            for i, (label, value) in enumerate(self.slices):
                fraction = value / total
                angle = fraction * 360.0
                color = PALETTE[i % len(PALETTE)]
                Color(*color)
                Ellipse(
                    pos=(cx - size / 2, cy - size / 2),
                    size=(size, size),
                    angle_start=start,
                    angle_end=start + angle,
                )
                start += angle


class LegendRow(BoxLayout):
    label_text = StringProperty("")
    swatch_color = ListProperty([1, 1, 1, 1])


class FinanceScreen(BoxLayout):
    summary_text = StringProperty("Доходы: 0  Расходы: 0  Баланс: 0")

    def on_kv_post(self, base_widget):
        self.refresh()

    def add_transaction(self, amount_text, tx_type, category, note):
        try:
            amount = float(amount_text.replace(",", "."))
            if amount <= 0:
                raise ValueError
        except ValueError:
            show_popup("Ошибка", "Введите корректную положительную сумму")
            return

        STORAGE.data["transactions"].append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "type": tx_type,
            "category": category,
            "amount": amount,
            "note": note.strip(),
        })
        STORAGE.save()
        self.ids.amount_input.text = ""
        self.ids.note_input.text = ""
        self.refresh()

    def delete_transaction(self, index):
        del STORAGE.data["transactions"][index]
        STORAGE.save()
        self.refresh()

    def refresh(self):
        container = self.ids.tx_list
        container.clear_widgets()
        for i, tx in enumerate(STORAGE.data["transactions"]):
            row = TaskRow()
            sign = "+" if tx["type"] == "Доход" else "-"
            row.text = f"{tx['date']}  {sign}{tx['amount']:.2f}  [{tx['category']}] {tx['note']}"
            row.index = i
            row.ids.check_btn.opacity = 0
            row.ids.check_btn.disabled = True
            row.ids.del_btn.bind(on_release=lambda w, idx=i: self.delete_transaction(idx))
            container.add_widget(row)

        income = sum(t["amount"] for t in STORAGE.data["transactions"] if t["type"] == "Доход")
        expense = sum(t["amount"] for t in STORAGE.data["transactions"] if t["type"] == "Расход")
        balance = income - expense
        self.summary_text = f"Доходы: {income:.2f}   Расходы: {expense:.2f}   Баланс: {balance:.2f}"

        expenses = {}
        for tx in STORAGE.data["transactions"]:
            if tx["type"] == "Расход":
                expenses[tx["category"]] = expenses.get(tx["category"], 0) + tx["amount"]
        self.ids.pie_chart.slices = list(expenses.items())

        legend = self.ids.legend_box
        legend.clear_widgets()
        for i, (label, value) in enumerate(expenses.items()):
            lg = LegendRow()
            lg.label_text = f"{label}: {value:.2f}"
            lg.swatch_color = list(PALETTE[i % len(PALETTE)])
            legend.add_widget(lg)


KV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mega.kv")


class MegaApp(App):
    def build(self):
        global STORAGE
        STORAGE = Storage(os.path.join(self.user_data_dir, "app_data.json"))
        Builder.load_file(KV_PATH)
        root = Builder.load_string(ROOT_KV)
        return root


ROOT_KV = """
TabbedPanel:
    do_default_tab: False
    tab_pos: "top_mid"

    TabbedPanelItem:
        text: "Калькулятор"
        CalculatorScreen:

    TabbedPanelItem:
        text: "Ежедневник"
        PlannerScreen:

    TabbedPanelItem:
        text: "Финансы"
        FinanceScreen:
"""


if __name__ == "__main__":
    MegaApp().run()
