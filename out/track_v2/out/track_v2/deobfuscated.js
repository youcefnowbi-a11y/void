import { r as n, u as p, l as W, d as X, g as G, s as H, j as e, L as Q, K as V, C as Z, e as _Component2, f as T, S as F, t as m } from "./index-CLrvWBIx.js";
import { C as _Component3 } from "./clock-CZp_LHFG.js";
function oe() {
  const [l, k] = n.useState("");
  const [i, w] = n.useState(false);
  const [a, _] = n.useState(null);
  const [S, b] = n.useState(null);
  const [g, C] = n.useState([]);
  const [D, P] = n.useState("");
  const [R, I] = n.useState(false);
  const [u, h] = n.useState(null);
  const [E, x] = n.useState(null);
  const q = p(W);
  const Y = p(X);
  const B = async (t, r) => {
    try {
      const s = await A({
        data: {
          orderNumber: t,
          token: r
        }
      });
      if (s.ok) {
        N({
          delivery_status: s.delivery_status,
          requests: s.requests
        });
      }
    } catch {}
  };
  const U = async t => {
    if (!a?._token) {
      m.error("Open this order from your secure link first.");
      return;
    }
    const r = (O[t] ?? "").trim();
    if (r.length < 2) {
      m.error("Please enter your account details first.");
      return;
    }
    z(t);
    try {
      const s = await $({
        data: {
          orderNumber: a.order_number,
          token: a._token,
          requestId: t,
          details: r
        }
      });
      if (s.ok) {
        m.success("Details submitted — we'll activate shortly.");
        v(o => ({
          ...o,
          [t]: ""
        }));
        j(null);
        await B(a.order_number, a._token);
      } else {
        m.error(s.error, {
          duration: 4000
        });
      }
    } catch (s) {
      m.error(s?.message ?? "Could not submit", {
        duration: 4000
      });
    } finally {
      z(null);
    }
  };
  const A = p(G);
  const $ = p(H);
  const [f, N] = n.useState(null);
  const [O, v] = n.useState({});
  const [L, z] = n.useState(null);
  const [K, j] = n.useState(null);
  n.useEffect(() => {
    try {
      const t = localStorage.getItem("shopee_orders_v1");
      if (t) {
        const r = JSON.parse(t).reverse();
        C(r);
        Promise.all(r.slice(0, 8).map(async s => {
          try {
            const o = await q({
              data: {
                orderNumber: s.orderNumber,
                token: s.token
              }
            });
            return {
              ...s,
              status: o?.order?.status
            };
          } catch {
            return s;
          }
        })).then(s => {
          C(o => {
            const c = new Map(s.map(d => [d.orderNumber, d]));
            return o.map(d => c.get(d.orderNumber) ?? d);
          });
        });
      }
    } catch {}
  }, []);
  const J = {
    pending: "Pending payment",
    processing: "Processing",
    delivered: "Ready — download PDF",
    expired: "Checkout expired",
    cancelled: "Cancelled",
    shipped: "Shipped"
  };
  return <div className="px-6 py-16"><div className="max-w-3xl mx-auto"><span className="text-xs font-mono uppercase tracking-widest text-accent">Support</span><h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mt-3">Track your order</h1><p className="text-muted-foreground mt-3">Enter your order ID to see your payment status. Your Product ID (received after payment) is required to reveal the actual product.</p><form onSubmit={async t => {
        t.preventDefault();
        w(true);
        b(null);
        _(null);
        h(null);
        x(null);
        P("");
        try {
          const r = l.trim().toUpperCase();
          const s = g.find(c => c.orderNumber === r)?.token;
          const o = await q({
            data: {
              orderNumber: r,
              ...(s ? {
                token: s
              } : {})
            }
          });
          if (!o.order) {
            b("No order found for that ID.");
          } else {
            const c = s ?? o.order.access_token ?? null;
            _({
              ...o.order,
              _token: c
            });
            N(null);
            if (c && o.order.status === "delivered") {
              try {
                const d = await A({
                  data: {
                    orderNumber: r,
                    token: c
                  }
                });
                if (d.ok && d.requests.length > 0) {
                  N({
                    delivery_status: d.delivery_status,
                    requests: d.requests
                  });
                }
              } catch {}
            }
          }
        } catch (r) {
          b(r?.message ?? "Lookup failed");
        } finally {
          w(false);
        }
      }} className="mt-8 grid sm:grid-cols-[1fr_auto] gap-3"><input value={l} onChange={t => k(t.target.value.toUpperCase())} placeholder="Order ID (e.g. ORDER1A2B3C4D5E6F)" required={true} maxLength={64} className="px-5 py-4 bg-card border border-border rounded-lg text-sm font-mono focus:border-accent focus:outline-none" /><button type="submit" disabled={i} className="px-8 py-4 bg-foreground text-background font-semibold rounded-lg hover:opacity-90">{i ? "…" : "Track"}</button></form>{g.length > 0 && <div className="mt-10"><h2 className="text-xs font-bold uppercase tracking-widest font-mono text-muted-foreground">Your recent orders on this device</h2><ul className="mt-3 space-y-2">{g.slice(0, 8).map(t => <li key={t.orderNumber}><Q to="/orders/$orderNumber" params={{
              orderNumber: t.orderNumber
            }} search={{
              t: t.token
            }} className="flex items-center justify-between gap-3 p-3 bg-card border border-border rounded-lg hover:border-accent transition-colors font-mono text-sm"><span className="truncate">#{t.orderNumber}</span><_Component status={t.status} /></Q></li>)}</ul></div>}{a && <div className="mt-10 space-y-6"><div className="border border-border bg-card rounded-2xl p-6 sm:p-8"><div className="flex items-center justify-between mb-4 gap-3"><h2 className="text-lg sm:text-xl font-bold font-mono truncate">#{a.order_number}</h2><span className="px-3 py-1 bg-accent/10 text-accent text-xs font-bold rounded-full whitespace-nowrap">{J[a.status] ?? a.status}</span></div><dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm"><div><dt className="text-[11px] uppercase tracking-widest text-muted-foreground font-mono">Total</dt><dd className="font-mono text-foreground mt-0.5">${Number(a.total).toFixed(2)} USDT</dd></div><div><dt className="text-[11px] uppercase tracking-widest text-muted-foreground font-mono">Payment</dt><dd className="mt-0.5">{a.paid_at ? <span className="text-foreground">Received · {new Date(a.paid_at).toLocaleString()}</span> : a.status === "expired" ? <span className="text-destructive">Checkout expired</span> : <span className="text-muted-foreground">Waiting for payment</span>}</dd></div><div className="sm:col-span-2"><dt className="text-[11px] uppercase tracking-widest text-muted-foreground font-mono">Items</dt><dd className="mt-1 space-y-1">{(a.items ?? []).map((t, r) => <div className="flex justify-between text-muted-foreground" key={r}><span className="truncate pr-2">{t.name} × {t.quantity ?? t.qty ?? 1}</span><span className="font-mono">${(Number(t.price ?? 0) * Number(t.quantity ?? t.qty ?? 1)).toFixed(2)}</span></div>)}</dd></div></dl></div>{f && f.requests.length > 0 && <div className="border border-border bg-card rounded-2xl p-6 sm:p-8"><div className="flex items-center gap-2"><V className="size-5 text-accent" /><h3 className="text-sm font-bold uppercase tracking-widest font-mono text-muted-foreground">Account activation status</h3></div><p className="text-sm text-muted-foreground mt-2">Below is the live status of each activation item in this order. To submit or update account details, open the order page.</p><div className="mt-4 space-y-3">{f.requests.map((t, r) => {
              const s = t.status === "activated";
              const o = t.status === "rejected";
              const c = t.status === "pending";
              const d = t.status === "awaiting_details";
              return <div className="p-4 rounded-xl border border-border bg-background" key={t.id}><div className="flex items-center justify-between gap-3 flex-wrap"><div className="font-bold text-sm flex items-center gap-2">{s && <Z className="size-4 text-accent" />}{o && <_Component2 className="size-4 text-destructive" />}{(c || d) && <_Component3 className="size-4 text-amber-500" />}{t.product_name}<span className="text-muted-foreground font-mono text-xs">#{r + 1}</span></div><span className={"text-[10px] px-2 py-0.5 rounded-full border uppercase font-mono " + (s ? "bg-accent/10 text-accent border-accent/30" : o ? "bg-destructive/10 text-destructive border-destructive/30" : c ? "bg-blue-500/10 text-blue-500 border-blue-500/30" : "bg-amber-500/10 text-amber-500 border-amber-500/30")}>{String(t.status).replace("_", " ")}</span></div>{t.admin_note && <p className="mt-2 text-xs"><span className="text-muted-foreground">Admin note: </span>{t.admin_note}</p>}{t.activation_instructions && (d || o) && <p className="text-xs text-muted-foreground mt-2 p-3 bg-secondary/40 rounded-lg border border-border whitespace-pre-wrap">{t.activation_instructions}</p>}{t.account_details && !d && <div className="mt-3"><div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Your submitted details</div><pre className="p-3 bg-secondary/40 border border-border rounded-lg text-xs whitespace-pre-wrap break-all font-mono max-w-full overflow-x-auto max-h-64 overflow-y-auto">{t.account_details}</pre></div>}{c && <p className="mt-2 text-xs text-muted-foreground inline-flex items-center gap-1"><T className="size-3 animate-spin" />Submitted — admin will activate shortly.</p>}{(d || o) && <div className="mt-3">{a._token ? K === t.id ? <div className="space-y-2"><textarea value={O[t.id] ?? ""} onChange={y => v(M => ({
                      ...M,
                      [t.id]: y.target.value
                    }))} rows={3} placeholder="Enter your account details (email, password, etc.)" className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm font-mono focus:border-accent focus:outline-none" /><div className="flex gap-2 flex-wrap"><button onClick={() => U(t.id)} disabled={L === t.id} className="px-4 py-2 bg-accent text-accent-foreground font-semibold rounded-lg hover:bg-accent/90 inline-flex items-center gap-2 text-sm disabled:opacity-50">{L === t.id ? <T className="size-4 animate-spin" /> : <F className="size-4" />}Send details</button><button onClick={() => {
                        j(null);
                        v(y => ({
                          ...y,
                          [t.id]: ""
                        }));
                      }} className="px-4 py-2 border border-border text-muted-foreground rounded-lg text-sm">Cancel</button></div></div> : <button onClick={() => j(t.id)} className="px-4 py-2 bg-accent text-accent-foreground font-semibold rounded-lg hover:bg-accent/90 inline-flex items-center gap-2 text-sm"><F className="size-4" />{o ? "Resubmit account details" : "Share account details"}</button> : <p className="text-xs text-amber-500">Open this order from its secure link (or from "Your recent orders" above) to share account details.</p>}</div>}</div>;
            })}</div></div>}{a.status === "delivered" && !a._token ? <div className="border border-border bg-card rounded-2xl p-6 sm:p-8 text-sm text-muted-foreground">To reveal product content, open this order from its secure link (saved at checkout) or from "Your recent orders" on the device where you placed it.</div> : a.status === "delivered" ? <div className="border border-border bg-card rounded-2xl p-6 sm:p-8"><h3 className="text-sm font-bold uppercase tracking-widest font-mono text-muted-foreground">Reveal product</h3><p className="text-sm text-muted-foreground mt-2">Enter the <b>Product ID</b> you received after payment to see the actual product content.</p>{a.delivered_summary?.length > 0 && <p className="text-[11px] text-muted-foreground mt-2">One Product ID unlocks all items in this order.</p>}<form onSubmit={async t => {
            t.preventDefault();
            I(true);
            x(null);
            h(null);
            try {
              const r = await Y({
                data: {
                  orderNumber: a.order_number,
                  token: a._token ?? "",
                  productId: D.trim()
                }
              });
              if (r.ok) {
                h(r.product);
              } else {
                x(r.error);
              }
            } catch (r) {
              x(r?.message ?? "Could not reveal product.");
            } finally {
              I(false);
            }
          }} className="mt-4 grid sm:grid-cols-[1fr_auto] gap-3"><input value={D} onChange={t => P(t.target.value.toUpperCase())} placeholder="Product ID (e.g. PROD1A2B3C4D)" required={true} maxLength={64} className="px-5 py-4 bg-background border border-border rounded-lg text-sm font-mono focus:border-accent focus:outline-none" /><button type="submit" disabled={R} className="px-6 py-4 bg-foreground text-background font-semibold rounded-lg hover:opacity-90 disabled:opacity-50">{R ? "…" : "Reveal"}</button></form>{E && <p className="mt-3 text-sm text-destructive">{E}</p>}{u && <div className="mt-5 space-y-3"><p className="font-mono text-xs text-muted-foreground">Product ID: {u.public_id} · {u.items.length} item{u.items.length === 1 ? "" : "s"}</p>{u.items.map((t, r) => <div className="p-4 bg-background border border-border rounded-lg" key={r}><span className="text-[11px] uppercase tracking-widest text-muted-foreground font-mono">{t.name}</span><pre className="mt-3 whitespace-pre-wrap break-all text-sm font-mono text-foreground">{t.content}</pre></div>)}</div>}</div> : <div className="border border-border bg-card rounded-2xl p-6 sm:p-8 text-sm text-muted-foreground">Product content is hidden until payment is received.</div>}</div>}{S && <div className="mt-8 p-6 border border-border rounded-xl bg-card"><p className="text-sm text-muted-foreground">{S}</p></div>}</div></div>;
}
function _Component({
  status: l
}) {
  if (!l) {
    return <span className="px-2 py-0.5 rounded-full bg-muted text-muted-foreground text-[10px] font-bold uppercase tracking-wider whitespace-nowrap">…</span>;
  }
  const i = {
    pending: {
      label: "Pending",
      cls: "bg-amber-500/15 text-amber-700 dark:text-amber-400"
    },
    processing: {
      label: "Pending",
      cls: "bg-amber-500/15 text-amber-700 dark:text-amber-400"
    },
    delivered: {
      label: "Paid",
      cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
    },
    shipped: {
      label: "Paid",
      cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
    },
    cancelled: {
      label: "Cancelled",
      cls: "bg-destructive/15 text-destructive"
    },
    expired: {
      label: "Expired",
      cls: "bg-muted text-muted-foreground"
    }
  }[l] ?? {
    label: l,
    cls: "bg-muted text-muted-foreground"
  };
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider whitespace-nowrap ${i.cls}`}>{i.label}</span>;
}
export { oe as component };