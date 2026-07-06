export default function TermsPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-4 p-6 text-sm leading-relaxed">
      <h1 className="text-2xl font-semibold">Terms of use</h1>
      <p className="text-[var(--muted)]">Rob&apos;s Finance — personal use only</p>
      <p>
        This application is provided for personal, non-commercial use by the account owner.
        Bank data is accessed read-only via Open Banking with your explicit consent at each
        connection.
      </p>
      <p>
        You are responsible for keeping your login credentials secure. The app does not initiate
        payments or transfers on your behalf.
      </p>
      <p>
        The service is provided as-is without warranty. Use of Open Banking is subject to your
        bank&apos;s and Enable Banking&apos;s terms.
      </p>
    </main>
  );
}
