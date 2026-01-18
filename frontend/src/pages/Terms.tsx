
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

const Terms = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <Link to="/auth">
            <Button variant="ghost" className="text-slate-300 hover:text-white">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Login
            </Button>
          </Link>
        </div>
        
        <Card className="bg-slate-800 border-slate-700">
          <CardHeader>
            <CardTitle className="text-2xl text-white">Terms of Service</CardTitle>
            <p className="text-slate-400">Last updated: {new Date().toLocaleDateString()}</p>
          </CardHeader>
          <CardContent className="prose prose-invert max-w-none">
            <div className="space-y-6 text-slate-300">
              <section>
                <h2 className="text-xl font-semibold text-white mb-3">1. Acceptance of Terms</h2>
                <p>
                  By accessing and using infraJet, you accept and agree to be bound by the terms and provision of this agreement.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-semibold text-white mb-3">2. Use License</h2>
                <p>
                  Permission is granted to temporarily download one copy of infraJet for personal, non-commercial transitory viewing only.
                  This is the grant of a license, not a transfer of title, and under this license you may not:
                </p>
                <ul className="list-disc ml-6 mt-2 space-y-1">
                  <li>modify or copy the materials</li>
                  <li>use the materials for any commercial purpose or for any public display</li>
                  <li>attempt to reverse engineer any software contained on infraJet</li>
                  <li>remove any copyright or other proprietary notations from the materials</li>
                </ul>
              </section>

              <section>
                <h2 className="text-xl font-semibold text-white mb-3">3. Disclaimer</h2>
                <p>
                  The materials on infraJet are provided on an 'as is' basis. infraJet makes no warranties, expressed or implied,
                  and hereby disclaims and negates all other warranties including without limitation, implied warranties or
                  conditions of merchantability, fitness for a particular purpose, or non-infringement of intellectual property
                  or other violation of rights.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-semibold text-white mb-3">4. Limitations</h2>
                <p>
                  In no event shall infraJet or its suppliers be liable for any damages (including, without limitation, damages for
                  loss of data or profit, or due to business interruption) arising out of the use or inability to use the materials
                  on infraJet, even if infraJet or an authorized representative has been notified orally or in writing of the possibility
                  of such damage. Because some jurisdictions do not allow limitations on implied warranties, or limitations of liability
                  for consequential or incidental damages, these limitations may not apply to you.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-semibold text-white mb-3">5. Accuracy of Materials</h2>
                <p>
                  The materials appearing on infraJet could include technical, typographical, or photographic errors. infraJet does not
                  warrant that any of the materials on its website are accurate, complete, or current. infraJet may make changes to
                  the materials contained on its website at any time without notice. However, infraJet does not make any commitment
                  to update the materials.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-semibold text-white mb-3">6. Links</h2>
                <p>
                  infraJet has not reviewed all of the sites linked to our website and is not responsible for the contents of any
                  such linked site. The inclusion of any link does not imply endorsement by infraJet of the site. Use of any such
                  linked website is at the user's own risk.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-semibold text-white mb-3">7. Modifications</h2>
                <p>
                  infraJet may revise these terms of service for its website at any time without notice. By using this website,
                  you are agreeing to be bound by the then current version of these terms of service.
                </p>
              </section>

              <section>
                <h2 className="text-xl font-semibold text-white mb-3">8. Governing Law</h2>
                <p>
                  These terms and conditions are governed by and construed in accordance with the laws of the jurisdiction in
                  which infraJet operates and you irrevocably submit to the exclusive jurisdiction of the courts in that state or location.
                </p>
              </section>
              <section>
                <h2 className="text-xl font-semibold text-white mb-3">8. Governing Law</h2>
                <p>
                  infraJet is designed, developed and is a property of Nexgen Tech Labs Limited, registered in England, United Kingtom.
                </p>
              </section>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Terms;
