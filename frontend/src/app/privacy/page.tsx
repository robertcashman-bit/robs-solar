export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-4 p-6 text-sm leading-relaxed">
      <h1 className="text-2xl font-semibold">Privacy policy</h1>
      <p className="text-[var(--muted)]">Rob&apos;s Finance — personal use only</p>
      <p>
        This app is a private finance dashboard. Bank connection data is read-only and used
        solely to display your account balances and transactions within the app.
      </p>
      <p>
        Open Banking credentials and session tokens are stored securely on the backend server.
        They are not shared with third parties except Enable Banking and your chosen bank during
        the authorised connection flow.
      </p>
      <p>
        For questions about this policy, contact the account owner via the email registered with
        Enable Banking.
      </p>
    </main>
  );
}
