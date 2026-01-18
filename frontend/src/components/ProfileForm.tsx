import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { UserProfile, UpdateProfileData, UserRole } from '@/services/profileService';

const profileSchema = z.object({
  full_name: z.string().min(1, 'Name is required'),
  business_email: z.string().email('Valid email is required'),
  role: z.enum([
    'Devops Engineer',
    'SRE', 
    'Infrastructure Engineer',
    'Cloud Engineer',
    'Lead Engineer',
    'Cloud Specialist'
  ], { required_error: 'Role is required' }),
  organization: z.string().optional(),
  linkedin_profile: z.string().url('Must be a valid URL').optional().or(z.literal('')),
});

interface ProfileFormProps {
  profile?: UserProfile | null;
  onSubmit: (data: UpdateProfileData) => Promise<void>;
  isLoading?: boolean;
}

const roleOptions: UserRole[] = [
  'Devops Engineer',
  'SRE',
  'Infrastructure Engineer', 
  'Cloud Engineer',
  'Lead Engineer',
  'Cloud Specialist'
];

export const ProfileForm = ({ profile, onSubmit, isLoading }: ProfileFormProps) => {
  const form = useForm<UpdateProfileData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: profile?.full_name || '',
      business_email: profile?.business_email || '',
      role: profile?.role || undefined,
      organization: profile?.organization || '',
      linkedin_profile: profile?.linkedin_profile || '',
    },
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <div className="grid gap-6">
          {/* Mandatory Fields */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-foreground">Required Information</h3>
            
            <FormField
              control={form.control}
              name="full_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name *</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="Enter your full name" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="business_email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email *</FormLabel>
                  <FormControl>
                    <Input {...field} type="email" placeholder="Enter your email" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="role"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Role *</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select your role" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {roleOptions.map((role) => (
                        <SelectItem key={role} value={role}>
                          {role}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          {/* Optional Fields */}
          <div className="space-y-4 pt-4 border-t border-border">
            <h3 className="text-lg font-medium text-foreground">Optional Information</h3>
            
            <FormField
              control={form.control}
              name="organization"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Organization</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="Enter your organization" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="linkedin_profile"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>LinkedIn Profile</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="https://linkedin.com/in/yourprofile" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </div>

        <div className="flex justify-end pt-6">
          <Button 
            type="submit" 
            disabled={isLoading}
            className="min-w-[120px]"
          >
            {isLoading ? 'Saving...' : 'Save Profile'}
          </Button>
        </div>
      </form>
    </Form>
  );
};