"""Bank Account Manager - Python + Streamlit (now with PIN security).

Run:  streamlit run bank_app.py

Every account has a 4-digit PIN. The PIN is asked for on EVERY operation:
deposit, withdraw, transfer (sender's PIN), check balance and delete.
The PIN is never stored as plain text: only a salted hash is saved.
3 wrong PINs lock the account for 5 minutes (saved in the file, so a
page refresh does not reset it).
"""

import hashlib
import hmac
import os
import secrets
import time

import streamlit as st

DATA_FILE = "accounts.txt"
FIRST_NUMBER = 1001
MAX_TRIES = 3
LOCK_SECONDS = 300


# ---------------------------------------------------------------- PIN helpers
def valid_pin_format(pin):
    return isinstance(pin, str) and len(pin) == 4 and pin.isdigit()


def hash_pin(pin, salt_hex):
    return hashlib.pbkdf2_hmac(
        "sha256", pin.encode(), bytes.fromhex(salt_hex), 100_000
    ).hex()


# -------------------------------------------------------------------- Account
class Account:
    def __init__(self, number, name, balance, salt="", pin_hash="",
                 fails=0, locked_until=0.0):
        self.number = number
        self.name = name
        self.balance = round(float(balance), 2)
        self.salt = salt
        self.pin_hash = pin_hash
        self.fails = fails
        self.locked_until = locked_until

    # --- PIN rules
    def set_pin(self, pin):
        self.salt = secrets.token_hex(16)
        self.pin_hash = hash_pin(pin, self.salt)
        self.fails = 0
        self.locked_until = 0.0

    def lock_seconds_left(self):
        return max(0, int(self.locked_until - time.time()))

    def check_pin(self, pin):
        """Returns (True/False, message). Caller must save the bank after."""
        if not self.pin_hash:
            return False, ("This account has no PIN (old file format). "
                           "Clear accounts.txt and create the account again.")
        left = self.lock_seconds_left()
        if left:
            return False, f"Account is locked. Try again in {left} seconds."
        if not valid_pin_format(pin):
            return False, "PIN must be exactly 4 digits."
        if hmac.compare_digest(hash_pin(pin, self.salt), self.pin_hash):
            self.fails = 0
            return True, "PIN correct."
        self.fails += 1
        if self.fails >= MAX_TRIES:
            self.fails = 0
            self.locked_until = time.time() + LOCK_SECONDS
            return False, (f"Wrong PIN {MAX_TRIES} times. "
                           f"Account locked for {LOCK_SECONDS // 60} minutes.")
        return False, f"Wrong PIN. {MAX_TRIES - self.fails} tries left."

    # --- money rules
    def deposit(self, amount):
        amount = round(amount, 2)
        if amount <= 0:
            return False
        self.balance = round(self.balance + amount, 2)
        return True

    def withdraw(self, amount):
        amount = round(amount, 2)
        if amount <= 0 or amount > self.balance:
            return False
        self.balance = round(self.balance - amount, 2)
        return True

    # --- file format: number|name|balance|salt|pin_hash|fails|locked_until
    def to_line(self):
        return "|".join([str(self.number), self.name, f"{self.balance:.2f}",
                         self.salt, self.pin_hash, str(self.fails),
                         f"{self.locked_until:.0f}"])

    @staticmethod
    def from_line(line):
        p = line.strip().split("|")
        if len(p) == 3:                       # old format, no PIN
            return Account(int(p[0]), p[1], float(p[2]))
        number, name, balance, salt, pin_hash, fails, locked = p
        return Account(int(number), name, float(balance), salt, pin_hash,
                       int(fails), float(locked))


# ----------------------------------------------------------------------- Bank
class Bank:
    def __init__(self, path=DATA_FILE):
        self.path = path
        self.accounts = []
        self.load_data()

    def load_data(self):
        """Read fresh from file every time. Broken lines are skipped."""
        self.accounts = []
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    self.accounts.append(Account.from_line(line))
                except ValueError:
                    continue

    def save_data(self):
        """Write to a temp file, then swap it in (safe saving)."""
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for acc in self.accounts:
                f.write(acc.to_line() + "\n")
        os.replace(tmp, self.path)

    def find_account(self, number):
        for acc in self.accounts:
            if acc.number == number:
                return acc
        return None

    def next_number(self):
        if not self.accounts:
            return FIRST_NUMBER
        return max(a.number for a in self.accounts) + 1

    def verify(self, number, pin):
        """Find the account and check its PIN. Saves the attempt counter."""
        acc = self.find_account(number)
        if acc is None:
            return None, "Account not found."
        ok, msg = acc.check_pin(pin)
        self.save_data()
        return (acc if ok else None), msg

    # --- operations (each one needs the PIN)
    def create_account(self, name, balance, pin, pin_again):
        name = name.strip()
        if not name or "|" in name:
            return False, "Enter a valid name (no empty name, no | sign)."
        if balance < 0:
            return False, "Opening balance cannot be negative."
        if not valid_pin_format(pin):
            return False, "PIN must be exactly 4 digits."
        if pin != pin_again:
            return False, "The two PINs do not match."
        acc = Account(self.next_number(), name, balance)
        acc.set_pin(pin)
        self.accounts.append(acc)
        self.save_data()
        return True, f"Account created. Account number: {acc.number}"

    def deposit(self, number, pin, amount):
        acc, msg = self.verify(number, pin)
        if acc is None:
            return False, msg
        if not acc.deposit(amount):
            return False, "Amount must be above zero."
        self.save_data()
        return True, f"Deposited. New balance: Rs {acc.balance:,.2f}"

    def withdraw(self, number, pin, amount):
        acc, msg = self.verify(number, pin)
        if acc is None:
            return False, msg
        if not acc.withdraw(amount):
            return False, "Amount must be above zero and within your balance."
        self.save_data()
        return True, f"Withdrawn. New balance: Rs {acc.balance:,.2f}"

    def transfer(self, from_no, pin, to_no, amount):
        if from_no == to_no:
            return False, "Both accounts must be different."
        receiver = self.find_account(to_no)
        if receiver is None:
            return False, "Receiver account not found."
        sender, msg = self.verify(from_no, pin)      # only SENDER's PIN
        if sender is None:
            return False, msg
        if not sender.withdraw(amount):
            return False, "Amount must be above zero and within your balance."
        receiver.deposit(amount)
        self.save_data()
        return True, (f"Transferred Rs {round(amount, 2):,.2f} to "
                      f"{receiver.name}. Your balance: Rs {sender.balance:,.2f}")

    def check_balance(self, number, pin):
        acc, msg = self.verify(number, pin)
        if acc is None:
            return False, msg
        return True, f"{acc.name}: Rs {acc.balance:,.2f}"

    def delete_account(self, number, pin, confirmed):
        acc, msg = self.verify(number, pin)
        if acc is None:
            return False, msg
        if not confirmed:
            return False, "Tick the confirmation box to delete."
        self.accounts.remove(acc)
        self.save_data()
        return True, f"Account {number} deleted."

    def public_list(self):
        """Balances are private, so the list shows only number and name."""
        return [{"Acc no": a.number, "Name": a.name} for a in self.accounts]


# ------------------------------------------------------------------------- UI
def show(result):
    ok, msg = result
    (st.success if ok else st.error)(msg)


def main():
    st.set_page_config(page_title="Bank Account Manager", page_icon="🏦")
    st.title("🏦 Bank Account Manager")
    st.caption("Demo project: no real money is involved. "
               "Every operation needs your 4-digit PIN.")

    bank = Bank()      # fresh read on every refresh
    menu = ["Create account", "Deposit", "Withdraw", "Transfer",
            "Check balance", "Show all accounts", "Delete account"]
    choice = st.sidebar.radio("Menu", menu)

    if choice == "Create account":
        with st.form("create"):
            name = st.text_input("Account holder name")
            bal = st.number_input("Opening balance (Rs)", min_value=0.0,
                                  step=100.0, format="%.2f")
            pin = st.text_input("Set a 4-digit PIN", type="password",
                                max_chars=4)
            pin2 = st.text_input("Confirm PIN", type="password", max_chars=4)
            if st.form_submit_button("Create"):
                show(bank.create_account(name, bal, pin, pin2))

    elif choice in ("Deposit", "Withdraw", "Check balance"):
        with st.form(choice):
            number = st.number_input("Account number", min_value=0, step=1)
            pin = st.text_input("PIN", type="password", max_chars=4)
            amount = 0.0
            if choice != "Check balance":
                amount = st.number_input("Amount (Rs)", min_value=0.0,
                                         step=100.0, format="%.2f")
            if st.form_submit_button(choice):
                if choice == "Deposit":
                    show(bank.deposit(int(number), pin, amount))
                elif choice == "Withdraw":
                    show(bank.withdraw(int(number), pin, amount))
                else:
                    show(bank.check_balance(int(number), pin))

    elif choice == "Transfer":
        with st.form("transfer"):
            from_no = st.number_input("Your account number", min_value=0,
                                      step=1)
            pin = st.text_input("Your PIN", type="password", max_chars=4)
            to_no = st.number_input("Send to account number", min_value=0,
                                    step=1)
            amount = st.number_input("Amount (Rs)", min_value=0.0,
                                     step=100.0, format="%.2f")
            if st.form_submit_button("Transfer"):
                show(bank.transfer(int(from_no), pin, int(to_no), amount))

    elif choice == "Show all accounts":
        rows = bank.public_list()
        if rows:
            st.table(rows)
            st.caption("Balances are hidden. Use Check balance with your PIN.")
        else:
            st.info("No accounts yet.")

    else:  # Delete account
        with st.form("delete"):
            number = st.number_input("Account number", min_value=0, step=1)
            pin = st.text_input("PIN", type="password", max_chars=4)
            sure = st.checkbox("Yes, I want to delete this account")
            if st.form_submit_button("Delete account"):
                show(bank.delete_account(int(number), pin, sure))


if __name__ == "__main__":
    main()
