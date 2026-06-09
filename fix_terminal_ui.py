with open('src/App.tsx', 'r') as f:
    content = f.read()

# Fix duplicate Terminal and Brain
import re
content = re.sub(r'Activity, Terminal, Brain,', 'Activity,', content)
content = re.sub(r'Terminal,', 'Terminal, BrainCircuit,', content)
# Ensure only one instance of each in the list
imports = ["Activity", "Terminal", "TrendingUp", "History", "ShieldCheck", "LogOut", "LogIn", "PlusCircle", "AlertTriangle", "Loader2", "ChevronRight", "Database", "Search", "User", "CheckCircle", "XCircle", "Mail", "Lock", "Calendar", "Wallet", "Clock", "DollarSign", "Zap", "Layers", "Send", "ExternalLink", "Crown", "Bell", "HelpCircle", "RefreshCw", "Server", "Menu", "X", "CreditCard", "BookOpen", "BrainCircuit", "Shield"]
content = re.sub(r'import \{.*?\} from \'lucide-react\';', 'import { ' + ', '.join(imports) + ' } from \'lucide-react\';', content, flags=re.DOTALL)

# Update nav label matching active tab
content = content.replace(
    'label="Terminal" active={activeTab === \'dashboard\'}',
    'label="Terminal" active={activeTab === \'dashboard\'} onClick={() => { setActiveTab(\'dashboard\'); setIsSidebarOpen(false); }}'
)
# (Removing extra duplicate logic if needed)

with open('src/App.tsx', 'w') as f:
    f.write(content)
