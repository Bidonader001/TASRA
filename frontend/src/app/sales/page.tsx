"use client";

import { useEffect, useState } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, Branch, Customer, Sale } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";

export default function SalesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [sales, setSales] = useState<Sale[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [printPrice, setPrintPrice] = useState(120);
  const [branchLabel, setBranchLabel] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ customer_id: "", branch_id: "", photo_count: "1", notes: "" });

  const selectedBranchPrice = isAdmin && form.branch_id
    ? branches.find((b) => b.id === Number(form.branch_id))?.price_per_photo ?? printPrice
    : printPrice;

  const totalPreview = Number(form.photo_count || 0) * selectedBranchPrice;

  const load = () => {
    Promise.all([api.getSales(), api.getPrintPrice()])
      .then(([salesRes, priceRes]) => {
        setSales(salesRes.items);
        setPrintPrice(priceRes.price_per_photo);
        setBranchLabel(priceRes.branch_name ?? user?.current_branch_name ?? null);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    api.getCustomers().then((r) => setCustomers(r.items));
    if (isAdmin) {
      api.getBranches().then(setBranches);
    }
  }, [isAdmin, user?.current_branch_name]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createSale({
        customer_id: Number(form.customer_id),
        photo_count: Number(form.photo_count),
        notes: form.notes || undefined,
        ...(isAdmin && form.branch_id ? { branch_id: Number(form.branch_id) } : {}),
      });
      toast({ title: "Print order recorded" });
      setShowForm(false);
      setForm({ customer_id: "", branch_id: "", photo_count: "1", notes: "" });
      load();
    } catch (err) {
      toast({ title: "Error", description: err instanceof Error ? err.message : "Failed", variant: "destructive" });
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="mobile-page-header">
          <div>
            <h1 className="text-2xl font-bold sm:text-3xl">Print Sales</h1>
            <p className="text-sm text-muted-foreground">
              {branchLabel ? `${branchLabel} — ` : ""}
              {formatCurrency(printPrice)} per photo
            </p>
          </div>
          <Button className="w-full sm:w-auto" onClick={() => setShowForm(!showForm)}>{showForm ? "Cancel" : "New Print Order"}</Button>
        </div>

        {showForm && (
          <Card>
            <CardHeader><CardTitle>Record Printed Photos</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={handleCreate} className="grid gap-4 md:grid-cols-2">
                {isAdmin && (
                  <div>
                    <Label>Branch</Label>
                    <select
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                      value={form.branch_id}
                      onChange={(e) => setForm({ ...form, branch_id: e.target.value })}
                      required
                    >
                      <option value="">Select branch</option>
                      {branches.filter((b) => b.is_active).map((b) => (
                        <option key={b.id} value={b.id}>{b.name} — {formatCurrency(b.price_per_photo)}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div>
                  <Label>Customer</Label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={form.customer_id}
                    onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
                    required
                  >
                    <option value="">Select customer</option>
                    {customers.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <Label>Number of Photos Printed</Label>
                  <Input
                    type="number"
                    min="1"
                    step="1"
                    value={form.photo_count}
                    onChange={(e) => setForm({ ...form, photo_count: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <Label>Notes (optional)</Label>
                  <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
                </div>
                <div className="flex items-end">
                  <div className="w-full rounded-lg border bg-secondary/30 p-4">
                    <p className="text-sm text-muted-foreground">Total amount</p>
                    <p className="text-2xl font-bold">{formatCurrency(totalPreview)}</p>
                    <p className="text-xs text-muted-foreground">
                      {form.photo_count || 0} × {formatCurrency(selectedBranchPrice)}
                    </p>
                  </div>
                </div>
                <div className="md:col-span-2">
                  <Button type="submit" className="w-full sm:w-auto">Save Print Order</Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex h-32 items-center justify-center">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="p-4 text-left">ID</th>
                    <th className="p-4 text-left">Branch</th>
                    <th className="p-4 text-left">Customer</th>
                    <th className="p-4 text-left">Employee</th>
                    <th className="p-4 text-left">Photos</th>
                    <th className="p-4 text-left">Price/Photo</th>
                    <th className="p-4 text-left">Total</th>
                    <th className="p-4 text-left">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {sales.map((s) => (
                    <tr key={s.id} className="border-b">
                      <td className="p-4">#{s.id}</td>
                      <td className="p-4">{s.branch_name || "—"}</td>
                      <td className="p-4">{s.customer_name || s.customer_id}</td>
                      <td className="p-4">{s.employee_name || s.employee_id}</td>
                      <td className="p-4 font-medium">{s.photo_count}</td>
                      <td className="p-4">{formatCurrency(s.price_per_photo)}</td>
                      <td className="p-4 font-semibold">{formatCurrency(s.amount)}</td>
                      <td className="p-4">{formatDate(s.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
