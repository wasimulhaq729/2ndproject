# Bank Account Management System (Streamlit version - fixed)
# Uses: functions, loops, if/else, file handling, classes and objects
# Run with:  streamlit run bank_app.py

import os
import streamlit as st

FILE_NAME = "accounts.txt"
TEMP_NAME = "accounts.tmp"


# ---------- Account class ----------
class Account:
    def __init__(self, acc_no, name, balance=0.0):
        self.acc_no = acc_no
        self.name = name
        self.balance = round(balance, 2)

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


# ---------- Bank class ----------
class Bank:
    def __init__(self):
        self.accounts = []

    def create_account(self, name, initial_balance):
        if len(self.accounts) == 0:
            acc_no = 1001
        else:
            acc_no = max(acc.acc_no for acc in self.accounts) + 1
        account = Account(acc_no, name, initial_balance)
        self.accounts.append(account)
        return account

    def find_account(self, acc_no):
        for account in self.accounts:
            if account.acc_no == acc_no:
                return account
        return None

    def transfer(self, from_no, to_no, amount):
        sender = self.find_account(from_no)
        receiver = self.find_account(to_no)
        if sender is None or receiver is None:
            return False, "Account not found."
        if from_no == to_no:
            return False, "Cannot transfer to the same account."
        if not sender.withdraw(amount):
            return False, "Transfer failed: invalid amount or low balance."
        receiver.deposit(amount)
        return True, "Transfer successful."

    def delete_account(self, acc_no):
        account = self.find_account(acc_no)
        if account is None:
            return False
        self.accounts.remove(account)
        return True


# ---------- File handling ----------
def save_data(bank):
    # Write to a temp file first, then replace - file never ends up half-written
    with open(TEMP_NAME, "w") as file:
        for acc in bank.accounts:
            file.write(f"{acc.acc_no},{acc.name},{acc.balance}\n")
    os.replace(TEMP_NAME, FILE_NAME)


def load_data(bank):
    open(FILE_NAME, "a").close()  # creates the file if it doesn't exist
    with open(FILE_NAME, "r") as file:
        for line in file:
            line = line.strip()
            if line == "":
                continue
            try:
                acc_no_text, rest = line.split(",", 1)
                name, balance_text = rest.rsplit(",", 1)  # name may contain commas
                bank.accounts.append(Account(int(acc_no_text), name, float(balance_text)))
            except ValueError:
                continue  # skip a broken line instead of crashing the app


# ---------- Streamlit helpers ----------
def done(message):
    # Show message after refresh so dropdowns and balances are up to date
    st.session_state["flash"] = message
    st.rerun()


def account_label(acc_no):
    acc = bank.find_account(acc_no)
    return f"{acc.acc_no} - {acc.name}"


# ---------- Streamlit UI ----------
st.set_page_config(page_title="Bank Account Management", page_icon="🏦")
st.title("🏦 Bank Account Management System")

# Always read fresh data from the file (no stale data, works across browser tabs)
bank = Bank()
load_data(bank)
account_numbers = [acc.acc_no for acc in bank.accounts]

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

menu = [
    "Create account",
    "Deposit",
    "Withdraw",
    "Transfer",
    "Check balance",
    "Show all accounts",
    "Delete account",
]
choice = st.sidebar.radio("Menu", menu)


if choice == "Create account":
    st.subheader("Create account")
    with st.form("create_form", clear_on_submit=True):
        name = st.text_input("Account holder name")
        amount = st.number_input("Opening balance", min_value=0.0, value=0.0, step=100.0, format="%.2f")
        submitted = st.form_submit_button("Create")
    if submitted:
        if name.strip() == "":
            st.error("Invalid name.")
        else:
            acc = bank.create_account(name.strip(), amount)
            save_data(bank)
            done(f"Account created. Your account number is {acc.acc_no}")

elif choice == "Deposit":
    st.subheader("Deposit")
    if len(bank.accounts) == 0:
        st.info("No accounts yet.")
    else:
        with st.form("deposit_form"):
            acc_no = st.selectbox("Account", account_numbers, format_func=account_label)
            amount = st.number_input("Amount to deposit", min_value=0.0, value=0.0, step=100.0, format="%.2f")
            submitted = st.form_submit_button("Deposit")
        if submitted:
            acc = bank.find_account(acc_no)
            if acc.deposit(amount):
                save_data(bank)
                done(f"Deposited. New balance of account {acc.acc_no}: {acc.balance:.2f}")
            else:
                st.error("Invalid amount.")

elif choice == "Withdraw":
    st.subheader("Withdraw")
    if len(bank.accounts) == 0:
        st.info("No accounts yet.")
    else:
        with st.form("withdraw_form"):
            acc_no = st.selectbox("Account", account_numbers, format_func=account_label)
            amount = st.number_input("Amount to withdraw", min_value=0.0, value=0.0, step=100.0, format="%.2f")
            submitted = st.form_submit_button("Withdraw")
        if submitted:
            acc = bank.find_account(acc_no)
            if acc.withdraw(amount):
                save_data(bank)
                done(f"Withdrawn. New balance of account {acc.acc_no}: {acc.balance:.2f}")
            else:
                st.error("Invalid amount or insufficient balance.")

elif choice == "Transfer":
    st.subheader("Transfer")
    if len(bank.accounts) < 2:
        st.info("You need at least 2 accounts to make a transfer.")
    else:
        with st.form("transfer_form"):
            from_no = st.selectbox("From account", account_numbers, format_func=account_label)
            to_no = st.selectbox("To account", account_numbers, index=1, format_func=account_label)
            amount = st.number_input("Amount", min_value=0.0, value=0.0, step=100.0, format="%.2f")
            submitted = st.form_submit_button("Transfer")
        if submitted:
            ok, message = bank.transfer(from_no, to_no, amount)
            if ok:
                save_data(bank)
                done(message)
            else:
                st.error(message)

elif choice == "Check balance":
    st.subheader("Check balance")
    if len(bank.accounts) == 0:
        st.info("No accounts yet.")
    else:
        acc_no = st.selectbox("Account", account_numbers, format_func=account_label)
        acc = bank.find_account(acc_no)
        st.write(f"**Account No:** {acc.acc_no}")
        st.write(f"**Name:** {acc.name}")
        st.write(f"**Balance:** {acc.balance:.2f}")

elif choice == "Show all accounts":
    st.subheader("All accounts")
    if len(bank.accounts) == 0:
        st.info("No accounts yet.")
    else:
        rows = []
        for acc in bank.accounts:
            rows.append(
                {
                    "Account No": acc.acc_no,
                    "Name": acc.name,
                    "Balance": f"{acc.balance:.2f}",
                }
            )
        st.table(rows)

elif choice == "Delete account":
    st.subheader("Delete account")
    if len(bank.accounts) == 0:
        st.info("No accounts yet.")
    else:
        with st.form("delete_form"):
            acc_no = st.selectbox("Account", account_numbers, format_func=account_label)
            confirm = st.checkbox("I am sure I want to delete this account")
            submitted = st.form_submit_button("Delete")
        if submitted:
            if not confirm:
                st.warning("Please tick the confirmation box first.")
            elif bank.delete_account(acc_no):
                save_data(bank)
                done("Account deleted.")
            else:
                st.error("Account not found.")
