import { supabase } from "@/integrations/supabase/client";

export type UserRole = 
  | 'Devops Engineer'
  | 'SRE'
  | 'Infrastructure Engineer'
  | 'Cloud Engineer'
  | 'Lead Engineer'
  | 'Cloud Specialist';

export interface UserProfile {
  id: string;
  full_name: string | null;
  business_email: string | null;
  role: UserRole | null;
  organization: string | null;
  linkedin_profile: string | null;
}

export interface UpdateProfileData {
  full_name: string;
  business_email: string;
  role: UserRole;
  organization?: string;
  linkedin_profile?: string;
}

export const profileService = {
  async getProfile(): Promise<UserProfile | null> {
    const { data, error } = await supabase
      .from('profiles')
      .select('*')
      .single();

    if (error) {
      console.error('Error fetching profile:', error);
      return null;
    }

    return data;
  },

  async updateProfile(updates: UpdateProfileData): Promise<{ error: any }> {
    const { error } = await supabase
      .from('profiles')
      .update(updates)
      .eq('id', (await supabase.auth.getUser()).data.user?.id);

    if (error) {
      console.error('Error updating profile:', error);
    }

    return { error };
  },

  async createProfile(profileData: UpdateProfileData): Promise<{ error: any }> {
    const user = (await supabase.auth.getUser()).data.user;
    if (!user) {
      return { error: new Error('User not authenticated') };
    }

    const { error } = await supabase
      .from('profiles')
      .insert({
        id: user.id,
        ...profileData
      });

    if (error) {
      console.error('Error creating profile:', error);
    }

    return { error };
  }
};