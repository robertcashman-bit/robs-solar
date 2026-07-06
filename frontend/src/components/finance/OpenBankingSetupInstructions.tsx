"use client";

type OpenBankingSetupInstructionsProps = {
  redirectUrlExample?: string;
};

export function OpenBankingSetupInstructions({
  redirectUrlExample = "https://robs-solar.vercel.app/open-banking/callback",
}: OpenBankingSetupInstructionsProps) {
  return (
    <details className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-4 py-3 text-sm">
      <summary className="cursor-pointer font-semibold">Open Banking Setup Instructions</summary>

      <div className="mt-4 space-y-6 text-[var(--muted)]">
        <section>
          <h3 className="font-medium text-[var(--foreground)]">
            GoCardless / Nordigen (recommended for UK banks — Lloyds, MBNA, Virgin)
          </h3>
          <ol className="mt-2 list-decimal space-y-2 pl-5">
            <li>
              Sign up at{" "}
              <a
                href="https://bankaccountdata.gocardless.com/overview/"
                className="underline"
                target="_blank"
                rel="noreferrer"
              >
                GoCardless Bank Account Data
              </a>{" "}
              (free for personal use).
            </li>
            <li>
              Create credentials and choose <strong>GoCardless / Nordigen</strong> as provider in the
              form below.
            </li>
            <li>
              Paste <strong>Secret ID</strong> as Client ID and <strong>Secret key</strong> as Client
              Secret. Use the same redirect URL as Enable Banking.
            </li>
            <li>Test connection, then connect Lloyds, MBNA and Virgin on the Connect banks page.</li>
          </ol>
        </section>

        <section>
          <h3 className="font-medium text-[var(--foreground)]">Enable Banking (EU banks — no GB on default account)</h3>
          <ol className="mt-2 list-decimal space-y-2 pl-5">
            <li>
              Sign in at{" "}
              <a
                href="https://enablebanking.com/sign-in/"
                className="underline"
                target="_blank"
                rel="noreferrer"
              >
                Enable Banking Control Panel
              </a>
              .
            </li>
            <li>
              Create an app (Sandbox first, then Restricted Production for real banks like Lloyds, Virgin,
              MBNA).
            </li>
            <li>
              Generate an RSA key pair locally and upload the <strong>public certificate</strong> (.crt) to
              Enable:
              <pre className="mt-2 overflow-x-auto rounded-lg bg-[var(--surface-sunken)] p-3 text-xs">
                {`openssl req -new -newkey rsa:2048 -nodes \\
  -keyout private.pem -x509 -days 730 \\
  -out public.crt -subj "/CN=Rob Finance"`}
              </pre>
            </li>
            <li>
              In Enable, add this exact <strong>Redirect URI</strong> to your app:
              <code className="mt-1 block rounded bg-[var(--surface-sunken)] px-2 py-1 text-xs">
                {redirectUrlExample}
              </code>
            </li>
            <li>
              Copy your <strong>Application ID</strong> into the form field labelled <em>Client ID</em>.
            </li>
            <li>
              Open <code className="rounded bg-[var(--surface-sunken)] px-1">private.pem</code> in a text
              editor and paste the full contents (including BEGIN/END lines) into <em>Client Secret</em>.
            </li>
            <li>
              Choose <strong>Sandbox</strong>, press Save, then Test Connection. Try connecting{" "}
              <strong>Mock ASPSP</strong> first.
            </li>
            <li>
              For real banks, switch to <strong>Live</strong>, complete Enable&apos;s production activation
              (link accounts in Control Panel), then connect your banks.
            </li>
          </ol>
        </section>

        <section>
          <h3 className="font-medium text-[var(--foreground)]">Where to paste each value (Enable Banking)</h3>
          <table className="mt-2 w-full border-collapse text-xs">
            <thead>
              <tr className="border-b border-[var(--border)] text-left">
                <th className="py-2 pr-3 font-medium text-[var(--foreground)]">Form field</th>
                <th className="py-2 font-medium text-[var(--foreground)]">Paste this from Enable Control Panel</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              <tr>
                <td className="py-2 pr-3 align-top">Client ID</td>
                <td className="py-2">Your app → Application ID</td>
              </tr>
              <tr>
                <td className="py-2 pr-3 align-top">Client Secret</td>
                <td className="py-2">Contents of private.pem (not your Enable password)</td>
              </tr>
              <tr>
                <td className="py-2 pr-3 align-top">Redirect URI</td>
                <td className="py-2">Same URL whitelisted under Redirect URLs in your Enable app</td>
              </tr>
              <tr>
                <td className="py-2 pr-3 align-top">Environment</td>
                <td className="py-2">Sandbox for testing; Live for Restricted Production</td>
              </tr>
              <tr>
                <td className="py-2 pr-3 align-top">Scopes</td>
                <td className="py-2">Account information and transactions (Enable handles this automatically)</td>
              </tr>
              <tr>
                <td className="py-2 pr-3 align-top">Webhook URL</td>
                <td className="py-2">Leave blank — Enable Banking does not require a webhook</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3 className="font-medium text-[var(--foreground)]">GoCardless / Nordigen (legacy only)</h3>
          <p className="mt-1">
            GoCardless Bank Account Data no longer accepts new signups. If you still have old keys: paste{" "}
            <strong>Secret ID</strong> as Client ID and <strong>Secret key</strong> as Client Secret.
          </p>
        </section>

        <section>
          <h3 className="font-medium text-[var(--foreground)]">Other providers</h3>
          <p className="mt-1">
            TrueLayer, Plaid, Yapily, and Tink are not supported in this app yet. For UK personal banks, use
            Enable Banking.
          </p>
        </section>
      </div>
    </details>
  );
}
