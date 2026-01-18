import { useEffect, useState } from 'react';
import { AdminLayout } from '@/components/admin/AdminLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { supabase } from '@/integrations/supabase/client';
import { Plus, Edit, Trash2, Copy } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { useAdminAuth } from '@/contexts/AdminAuthContext';

interface PromoCode {
  id: string;
  code: string;
  description: string;
  discount_type: 'percentage' | 'fixed_amount' | 'credits';
  discount_value: number;
  max_uses: number | null;
  current_uses: number;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
}

const PromoCodes = () => {
  const [promoCodes, setPromoCodes] = useState<PromoCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newPromoCode, setNewPromoCode] = useState({
    code: '',
    description: '',
    discount_type: 'percentage' as const,
    discount_value: 0,
    max_uses: '',
    expires_at: '',
  });
  const { toast } = useToast();
  const { adminUser } = useAdminAuth();

  useEffect(() => {
    fetchPromoCodes();
  }, []);

  const fetchPromoCodes = async () => {
    try {
      const { data, error } = await supabase
        .from('promo_codes')
        .select('*')
        .order('created_at', { ascending: false });

      if (error) throw error;
      setPromoCodes((data || []) as PromoCode[]);
    } catch (error) {
      console.error('Error fetching promo codes:', error);
      toast({
        title: "Error",
        description: "Failed to fetch promo codes",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const createPromoCode = async () => {
    try {
      const { error } = await supabase
        .from('promo_codes')
        .insert({
          code: newPromoCode.code.toUpperCase(),
          description: newPromoCode.description,
          discount_type: newPromoCode.discount_type,
          discount_value: newPromoCode.discount_value,
          max_uses: newPromoCode.max_uses ? parseInt(newPromoCode.max_uses) : null,
          expires_at: newPromoCode.expires_at || null,
          created_by: adminUser?.id,
        });

      if (error) throw error;

      await fetchPromoCodes();
      setShowCreateDialog(false);
      setNewPromoCode({
        code: '',
        description: '',
        discount_type: 'percentage',
        discount_value: 0,
        max_uses: '',
        expires_at: '',
      });
      
      toast({
        title: "Success",
        description: "Promo code created successfully",
      });
    } catch (error) {
      console.error('Error creating promo code:', error);
      toast({
        title: "Error",
        description: "Failed to create promo code",
        variant: "destructive",
      });
    }
  };

  const togglePromoCodeStatus = async (id: string, currentStatus: boolean) => {
    try {
      const { error } = await supabase
        .from('promo_codes')
        .update({ is_active: !currentStatus })
        .eq('id', id);

      if (error) throw error;
      
      await fetchPromoCodes();
      toast({
        title: "Success",
        description: `Promo code ${!currentStatus ? 'activated' : 'deactivated'} successfully`,
      });
    } catch (error) {
      console.error('Error toggling promo code status:', error);
      toast({
        title: "Error",
        description: "Failed to update promo code status",
        variant: "destructive",
      });
    }
  };

  const copyToClipboard = (code: string) => {
    navigator.clipboard.writeText(code);
    toast({
      title: "Copied",
      description: `Promo code "${code}" copied to clipboard`,
    });
  };

  const generateRandomCode = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let result = '';
    for (let i = 0; i < 8; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setNewPromoCode(prev => ({ ...prev, code: result }));
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Promo Codes</h1>
            <p className="text-muted-foreground">
              Create and manage promotional discount codes
            </p>
          </div>
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Create Promo Code
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Create New Promo Code</DialogTitle>
                <DialogDescription>
                  Set up a new promotional discount code for users
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="code">Promo Code</Label>
                  <div className="flex gap-2">
                    <Input
                      id="code"
                      value={newPromoCode.code}
                      onChange={(e) => setNewPromoCode(prev => ({ ...prev, code: e.target.value }))}
                      placeholder="SAVE20"
                      className="uppercase"
                    />
                    <Button variant="outline" onClick={generateRandomCode}>
                      Generate
                    </Button>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Input
                    id="description"
                    value={newPromoCode.description}
                    onChange={(e) => setNewPromoCode(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="20% off for new users"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Discount Type</Label>
                    <Select 
                      value={newPromoCode.discount_type} 
                      onValueChange={(value: any) => setNewPromoCode(prev => ({ ...prev, discount_type: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="percentage">Percentage</SelectItem>
                        <SelectItem value="fixed_amount">Fixed Amount</SelectItem>
                        <SelectItem value="credits">Credits</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="discount_value">
                      Value {newPromoCode.discount_type === 'percentage' ? '(%)' : 
                             newPromoCode.discount_type === 'fixed_amount' ? '($)' : '(Credits)'}
                    </Label>
                    <Input
                      id="discount_value"
                      type="number"
                      value={newPromoCode.discount_value}
                      onChange={(e) => setNewPromoCode(prev => ({ ...prev, discount_value: parseFloat(e.target.value) || 0 }))}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="max_uses">Max Uses (optional)</Label>
                    <Input
                      id="max_uses"
                      type="number"
                      value={newPromoCode.max_uses}
                      onChange={(e) => setNewPromoCode(prev => ({ ...prev, max_uses: e.target.value }))}
                      placeholder="Unlimited"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="expires_at">Expires (optional)</Label>
                    <Input
                      id="expires_at"
                      type="datetime-local"
                      value={newPromoCode.expires_at}
                      onChange={(e) => setNewPromoCode(prev => ({ ...prev, expires_at: e.target.value }))}
                    />
                  </div>
                </div>

                <div className="flex gap-2 pt-4">
                  <Button onClick={createPromoCode} className="flex-1">
                    Create Promo Code
                  </Button>
                  <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Active Promo Codes</CardTitle>
            <CardDescription>
              Manage promotional codes and track their usage
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center py-8">Loading promo codes...</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Discount</TableHead>
                    <TableHead>Usage</TableHead>
                    <TableHead>Expires</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {promoCodes.map((promo) => (
                    <TableRow key={promo.id}>
                      <TableCell className="font-mono font-medium">
                        <div className="flex items-center gap-2">
                          {promo.code}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => copyToClipboard(promo.code)}
                            className="h-6 w-6 p-0"
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell>{promo.description}</TableCell>
                      <TableCell>
                        {promo.discount_type === 'percentage' ? `${promo.discount_value}%` :
                         promo.discount_type === 'fixed_amount' ? `$${promo.discount_value}` :
                         `${promo.discount_value} credits`}
                      </TableCell>
                      <TableCell>
                        {promo.current_uses}{promo.max_uses ? `/${promo.max_uses}` : ''}
                      </TableCell>
                      <TableCell>
                        {promo.expires_at ? new Date(promo.expires_at).toLocaleDateString() : 'Never'}
                      </TableCell>
                      <TableCell>
                        <Badge variant={promo.is_active ? 'default' : 'secondary'}>
                          {promo.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex space-x-2">
                          <Button variant="outline" size="sm">
                            <Edit className="h-3 w-3" />
                          </Button>
                          <Button 
                            variant="outline" 
                            size="sm"
                            onClick={() => togglePromoCodeStatus(promo.id, promo.is_active)}
                          >
                            {promo.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
};

export default PromoCodes;