# Silvi Core - Business Logic & Architecture Audit

## Overview
This document focuses on the core business logic, domain models, architecture patterns, and feature development areas of the Silvi reforestation platform. Designed for reasoning models to understand and improve the system architecture.

**Focus Areas**: Reforestation Logic, Asset Management, Project/Campaign Management, User Permissioning, Frontend Architecture

---

# CORE BUSINESS DOMAIN MODELS

## Tree Management & Reforestation Logic

### Tree Model - The Core Asset
**Path**: `django-backend/core/models.py`
**Purpose**: Central model representing planted trees with lifecycle tracking

```python
class Tree(models.Model):
    # Backwards compatibility for coord system
    coord = models.ForeignKey(Coord, on_delete=models.SET_NULL, null=True, blank=True)

    # Core metadata - Geographic location
    point = models.PointField(geography=True, null=True, blank=True)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, null=True, blank=True)

    # Source tracking - Where did this tree come from?
    source_seed_bed = models.ForeignKey(SeedBed, on_delete=models.CASCADE, null=True, blank=True)
    source_potting_bed = models.ForeignKey(PottedBed, on_delete=models.CASCADE, null=True, blank=True)

    # Species Information
    species = models.ForeignKey(basemodels.Species, on_delete=models.SET_NULL, null=True, blank=True)

    # Physical Characteristics
    health = models.IntegerField(choices=TREE_HEALTH_CHOICES, default=1, null=True, blank=True)
    # TREE_HEALTH_CHOICES: (1, 'Healthy'), (2, 'Unhealthy'), (3, 'Dead')

    height_unit = models.CharField(max_length=256, blank=True, null=True)
    height = models.IntegerField(null=True, blank=True)
    trunk_diameter = models.IntegerField(verbose_name="Trunk Diameter (in cm)", null=True, blank=True)

    # Lifecycle stage
    start_stage = models.CharField(max_length=256, blank=True, null=True, choices=CLAIM_TYPE_CHOICES)
    
    # Verification status - Critical for carbon credit validation
    verified = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.species.species_common_name} tree {self.pk}' if self.species else super().__str__()

    @property
    def interactions(self):
        """All logs/interactions for this tree"""
        return Log.objects.filter(tree=self).order_by('timestamp')

    def images(self):
        """All images associated with this tree"""
        return Image.objects.filter(log__tree=self)

    def tree_genesis(self, user, images, notes):
        """Creates the first interaction for a tree - marks it as verified"""
        log = Log(
            point=self.point,
            tree=self,
            user=user,
            event=2,  # Tree planting event
            claim_type=4,  # Proof of planting
            number_of_claims=1,
            goal=self.goal,
            notes=notes,
        )
        
        # Mark the tree as verified
        self.verified = True
        self.save()
        
        return Log.process_claim_save(log, images)
```

### Species Management
**Path**: `django-backend/core/basemodels.py`
**Purpose**: Biodiversity tracking and species-specific management

```python
class Species(models.Model):
    species_common_name = models.CharField(max_length=256, blank=True, null=True)
    species_scientific_name = models.CharField(max_length=256, blank=True, null=True)
    genus = models.CharField(max_length=256, blank=True, null=True)
    family = models.CharField(max_length=256, blank=True, null=True)
    native_to = models.CharField(max_length=256, blank=True, null=True)
    
    # Taxonomic classification
    taxon_id = models.CharField(max_length=256, blank=True, null=True)
    
    # Growth characteristics
    growth_form = models.CharField(max_length=256, blank=True, null=True)
    max_height = models.IntegerField(null=True, blank=True)
    
    # Environmental requirements
    climate_zone = models.CharField(max_length=256, blank=True, null=True)
    soil_type = models.CharField(max_length=256, blank=True, null=True)
    water_requirements = models.CharField(max_length=256, blank=True, null=True)
    
    # Carbon sequestration potential
    carbon_sequestration_rate = models.FloatField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.species_common_name} ({self.species_scientific_name})"
```

---

# NURSERY & PROPAGATION MANAGEMENT

## Seed Bed Management
**Path**: `django-backend/core/models.py`
**Purpose**: Track seed germination and early growth stages

```python
class SeedBed(models.Model):
    # Location tracking
    point = models.PointField(geography=True, null=True, blank=True)
    coord = models.ForeignKey(Coord, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Bed characteristics
    polygon = models.MultiPolygonField(geography=True, null=True, blank=True)
    area = models.FloatField(null=True, blank=True)  # in square meters
    
    # Species and capacity
    species = models.ForeignKey(Species, on_delete=models.SET_NULL, null=True, blank=True)
    capacity = models.IntegerField(null=True, blank=True)  # number of seeds
    current_count = models.IntegerField(default=0)
    
    # Lifecycle tracking
    sowing_date = models.DateTimeField(null=True, blank=True)
    germination_date = models.DateTimeField(null=True, blank=True)
    transplant_ready_date = models.DateTimeField(null=True, blank=True)
    
    # Management
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, null=True, blank=True)
    nursery = models.ForeignKey('user.Nursery', on_delete=models.CASCADE, null=True, blank=True)
    
    # Status tracking
    is_active = models.BooleanField(default=True)
    germination_rate = models.FloatField(null=True, blank=True)  # percentage
    
    def __str__(self):
        return f"SeedBed {self.pk} - {self.species.species_common_name if self.species else 'Unknown'}"
    
    @property
    def germination_percentage(self):
        if self.capacity and self.current_count:
            return (self.current_count / self.capacity) * 100
        return 0
```

## Potted Bed Management
**Path**: `django-backend/core/models.py`
**Purpose**: Track saplings in individual containers before field planting

```python
class PottedBed(models.Model):
    # Location and physical characteristics
    point = models.PointField(geography=True, null=True, blank=True)
    coord = models.ForeignKey(Coord, on_delete=models.SET_NULL, null=True, blank=True)
    polygon = models.MultiPolygonField(geography=True, null=True, blank=True)
    
    # Source tracking - where did these saplings come from?
    source_seed_bed = models.ForeignKey(SeedBed, on_delete=models.CASCADE, null=True, blank=True)
    
    # Sapling characteristics
    species = models.ForeignKey(Species, on_delete=models.SET_NULL, null=True, blank=True)
    capacity = models.IntegerField(null=True, blank=True)
    current_count = models.IntegerField(default=0)
    
    # Growth tracking
    potting_date = models.DateTimeField(null=True, blank=True)
    transplant_ready_date = models.DateTimeField(null=True, blank=True)
    average_height = models.FloatField(null=True, blank=True)  # in cm
    
    # Management
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, null=True, blank=True)
    nursery = models.ForeignKey('user.Nursery', on_delete=models.CASCADE, null=True, blank=True)
    
    # Care requirements
    watering_frequency = models.CharField(max_length=100, null=True, blank=True)
    fertilizer_schedule = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"PottedBed {self.pk} - {self.species.species_common_name if self.species else 'Unknown'}"
    
    @property
    def survival_rate(self):
        """Calculate survival rate from source seed bed"""
        if self.source_seed_bed and self.source_seed_bed.current_count:
            return (self.current_count / self.source_seed_bed.current_count) * 100
        return 0
```

---

# PROJECT & CAMPAIGN MANAGEMENT

## Goal System - Reforestation Targets
**Path**: `django-backend/core/models.py`
**Purpose**: Define reforestation targets and track progress

```python
class Goal(models.Model):
    # Timeline
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    active = models.BooleanField(default=True)
    
    # Target metrics
    target = models.IntegerField(default=0)  # number of trees to plant
    
    # Methodology and verification
    methodology = models.ForeignKey('Methodology', on_delete=models.CASCADE, null=True, blank=True)
    
    # Blockchain integration
    pool_address = models.CharField(max_length=256, blank=True, null=True)
    chain = models.CharField(max_length=50, choices=CHAIN_CHOICES, default='celo')
    token_id = models.CharField(max_length=256, blank=True, null=True)
    
    # Hierarchy - goals can be part of larger super goals
    super_goal = models.ForeignKey('SuperGoal', on_delete=models.CASCADE, null=True, blank=True)
    
    # GoodCollective integration
    goodcollective_pool_id = models.CharField(max_length=256, blank=True, null=True)
    
    # Dynamic conditions for goal completion
    conditions_json = models.JSONField(null=True, blank=True)
    
    def __str__(self):
        return f"Goal {self.pk} - Target: {self.target} trees"
    
    @property
    def trees_planted(self):
        """Count of verified trees associated with this goal"""
        return Tree.objects.filter(goal=self, verified=True).count()
    
    @property
    def completion_percentage(self):
        if self.target > 0:
            return (self.trees_planted / self.target) * 100
        return 0
    
    @property
    def is_completed(self):
        return self.trees_planted >= self.target
```

## Campaign System - Marketing & Engagement
**Path**: `django-backend/core/models.py`
**Purpose**: Public-facing campaigns to drive engagement and funding

```python
class Campaign(models.Model):
    # Basic information
    title = models.CharField(max_length=256)
    description = models.TextField()
    
    # Geographic targeting
    countries = models.JSONField(null=True, blank=True)  # list of country codes
    bioregions = models.JSONField(null=True, blank=True)
    ecoregions = models.JSONField(null=True, blank=True)
    
    # Campaign organization
    collection = models.ForeignKey('CampaignCollection', on_delete=models.CASCADE, null=True, blank=True)
    cover_image = models.ForeignKey('Image', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Linked reforestation work
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, null=True, blank=True)
    zone = models.ForeignKey('Zone', on_delete=models.CASCADE, null=True, blank=True)
    
    # Instructions for participants
    instructions = models.TextField(null=True, blank=True)
    instructions_video_url = models.URLField(null=True, blank=True)
    
    def __str__(self):
        return self.title
    
    @property
    def progress_percentage(self):
        if self.goal:
            return self.goal.completion_percentage
        return 0

class CampaignPartner(models.Model):
    """Organizations partnering on campaigns"""
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='partners')
    name = models.CharField(max_length=256)
    link = models.URLField(null=True, blank=True)
    logo = models.ForeignKey('Image', on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} - {self.campaign.title}"
```

---

# VERIFICATION & CLAIMS SYSTEM

## Log System - Activity Tracking
**Path**: `django-backend/core/models.py`
**Purpose**: Track all activities and claims in the reforestation process

```python
class Log(models.Model):
    # Temporal and spatial data
    timestamp = models.DateTimeField(auto_now_add=True)
    point = models.PointField(geography=True, null=True, blank=True)
    
    # What was done?
    event = models.IntegerField(choices=LOG_EVENT_CHOICES, null=True, blank=True)
    # LOG_EVENT_CHOICES: (0, 'Seed Bed Registration'), (1, 'Potted Bed Registration'), (2, 'Tree Registration')
    
    # Associated objects
    tree = models.ForeignKey(Tree, on_delete=models.CASCADE, null=True, blank=True)
    seed_bed = models.ForeignKey(SeedBed, on_delete=models.CASCADE, null=True, blank=True)
    potted_bed = models.ForeignKey(PottedBed, on_delete=models.CASCADE, null=True, blank=True)
    
    # Who did it?
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Measurements and observations
    notes = models.TextField(blank=True, null=True)
    height = models.IntegerField(null=True, blank=True)
    measure = models.IntegerField(choices=MEASURE_CHOICES, null=True, blank=True)
    value = models.IntegerField(null=True, blank=True)
    
    # Progress tracking
    on_track = models.BooleanField(default=True)
    
    # Claims and verification
    claim_type = models.IntegerField(choices=CLAIM_TYPE_CHOICES, null=True, blank=True)
    number_of_claims = models.IntegerField(default=1)
    claim_amount = models.FloatField(null=True, blank=True)
    claim_created = models.BooleanField(default=False)
    claim_approved = models.BooleanField(default=False)
    
    # Blockchain integration
    json_cid = models.CharField(max_length=256, blank=True, null=True)  # IPFS hash
    
    # Approval workflow
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_logs')
    
    # Goal association
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, null=True, blank=True)
    
    # Grouping related logs
    log_group = models.ForeignKey('LogGroup', on_delete=models.CASCADE, null=True, blank=True)
    
    # Media attachments
    images = models.ManyToManyField('Image', blank=True)
    videos = models.ManyToManyField('Video', blank=True)
    
    # Observational data
    directional_photo = models.ForeignKey('DirectionalPhoto', on_delete=models.SET_NULL, null=True, blank=True)
    panorama = models.ForeignKey('Panorama', on_delete=models.SET_NULL, null=True, blank=True)

# Claim types represent different stages in the reforestation process
CLAIM_TYPE_CHOICES = (
    (0, 'Proof of Sowing'),
    (1, 'Proof of Germination'), 
    (2, 'Proof of Potting'),
    (3, 'Proof of Maturity'),
    (4, 'Proof of Planting'),
    (5, 'Before Planting'),
    (10, '10: Proof of Sowing Seed Generic'),
    (20, '20: Proof of Germination Generic'),
    (21, '21: Proof of Planting Sapling'),
    (30, '30: Proof of Planting Generic'),
    (40, '40: Proof of Maturity/Reporting Generic'),
    (41, '41: Proof of Maturity/Reporting (3 months)'),
)
```

---

# USER MANAGEMENT & AUTHENTICATION SYSTEM

## Multi-Modal Authentication Architecture

Silvi implements a comprehensive authentication system supporting:
1. **Traditional Email/Password** authentication
2. **Google OAuth 2.0** integration 
3. **Web3 Wallet Authentication** (Celo, Arbitrum)
4. **Hybrid accounts** (users can link multiple auth methods)

## User Profile System
**Path**: `django-backend/user/models.py`
**Purpose**: Extended user profiles with multi-auth support

```python
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Personal information
    bio = models.TextField(max_length=1024, blank=True)
    location = models.CharField(max_length=512, blank=True)
    
    # Social media handles
    twitter_handle = models.CharField(max_length=100, blank=True, null=True, 
                                    help_text='Enter your handle WITHOUT an "@" symbol')
    instagram_handle = models.CharField(max_length=100, blank=True, null=True,
                                      help_text='Enter your handle WITHOUT an "@" symbol')
    
    def __str__(self):
        return f"Profile for {self.user.username}"
    
    @property
    def related_wallet_address(self):
        """Get primary wallet address for this user"""
        return WalletAddress.objects.filter(user=self.user).first().address

class WalletAddress(models.Model):
    """Multi-chain wallet addresses with provider tracking"""
    CHAINS = [
        ('celo', 'CELO'),
        ('arbitrum', 'Arbitrum'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.CharField(max_length=50)  # Ethereum address format
    chain = models.CharField(max_length=50, choices=CHAINS, default='celo')
    provider = models.CharField(max_length=50, blank=True, null=True)  # MetaMask, WalletConnect, etc.
    
    class Meta:
        unique_together = [['user', 'address']]
        verbose_name = "Wallet Address"
        verbose_name_plural = "Wallet Addresses"
    
    def set_nursery_address(self):
        """Auto-assign wallet to user's default nursery"""
        default_nursery = Nursery.get_default_nursery(self.user)
        
        if default_nursery is None:
            default_nursery = Nursery.create_default_nursery(self.user)
        
        default_nursery.wallet_address = self
        default_nursery.save()
        
        return default_nursery
    
    def __str__(self):
        return f"{self.user.username} - {self.address}"
```

## Authentication Flows

### 1. Traditional Username/Password Authentication
**Path**: `django-backend/user/views.py` - `UsernamePasswordLoginView`

```python
class UsernamePasswordLoginView(APIView):
    permission_classes = (permissions.AllowAny,)
    
    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')
        
        user = get_object_or_404(User, username=username)
        
        # Check if user has a password (not OAuth/wallet-only)
        if not user.has_usable_password():
            return Response({
                'detail': "It seems you signed up with another provider such as Google or Wallet and haven't set a password. Please use that provider to login"
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not user.check_password(password):
            return Response({'detail': 'Wrong password'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        user_logged_in.send(sender=user.__class__, request=request, user=user)
        
        return Response({
            'access': str(refresh.access_token), 
            'refresh': str(refresh)
        }, status=status.HTTP_200_OK)
```

### 2. Google OAuth Integration
**Path**: `django-backend/user/views.py` - `GoogleLoginView`

```python
class GoogleLoginView(APIView):
    permission_classes = (permissions.AllowAny,)
    
    def post(self, request, *args, **kwargs):
        id_token_str = request.data.get('id_token')
        email = request.data.get('email')
        given_name = request.data.get('given_name', '')
        family_name = request.data.get('family_name', '')
        
        # Handle existing authenticated users linking Google
        if request.user.is_authenticated:
            if request.user.email and request.user.email != email:
                return Response({
                    'detail': f'The gmail email you are trying to connect ({email}) is different from the one set in this account ({request.user.email}).'
                }, status=status.HTTP_400_BAD_REQUEST)
            user = request.user
            
        # Handle new users or existing Google users
        elif request.user.is_anonymous:
            if User.objects.filter(email=email).exists():
                user = User.objects.filter(email=email).first()
            else:
                # Create new user with Google data
                user = User(
                    email=email,
                    username=email,
                    first_name=given_name,
                    last_name=family_name,
                    is_active=True
                )
                user.set_unusable_password()  # Google OAuth only
                
                # Create onboarding notifications
                update_profile_notification = Notification(
                    user=user,
                    notification_type='update_profile',
                    title='User Profile',
                    message='Update your profile information'
                )
                
                connect_wallet_notification = Notification(
                    user=user,
                    notification_type='connect_wallet',
                    title='Connect wallet',
                    message='Connect to earn money through Silvi'
                )
        
        # Verify Google ID token
        try:
            payload = id_token.verify_oauth2_token(id_token_str, requests.Request())
            if payload.get('email') != email:
                return Response({
                    'detail': f'The provided email ({email}) does not match the one from the token ({payload.get("email")})'
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'detail': 'Authentication of Google token failed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user.save()
        
        # Ensure profile exists
        if not Profile.objects.filter(user=user).exists():
            Profile.objects.create(user=user)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        user_logged_in.send(sender=user.__class__, request=request, user=user)
        
        return Response({
            'access': str(refresh.access_token), 
            'refresh': str(refresh)
        }, status=status.HTTP_200_OK)
```

### 3. Web3 Wallet Authentication
**Path**: `django-backend/user/wallet_auth.py` - Complete cryptographic verification

```python
class WalletAuthentication:
    celo_url = 'https://forno.celo.org' if settings.IS_MAINNET else 'https://alfajores-forno.celo-testnet.org'
    arbitrum_url = 'https://arb1.arbitrum.io/rpc' if settings.IS_MAINNET else 'https://sepolia-rollup.arbitrum.io/rpc'
    
    def authenticate(self, public_address, signature, timestamp, chain):
        """Authenticate existing wallet user"""
        try:
            wa = WalletAddress.objects.get(address__iexact=public_address, chain=chain)
        except WalletAddress.DoesNotExist as e:
            raise exceptions.AuthenticationFailed('User does not exist') from e
            
        self.verify(public_address, signature, timestamp, chain)
        return wa.user
    
    def connect_address(self, user, public_address, signature, timestamp, chain, provider=None):
        """Connect new wallet to existing user or create new user"""
        # Prevent wallet address hijacking
        exists = WalletAddress.objects.filter(
            address__iexact=public_address,
            chain=chain
        ).exclude(user=user.id).exists()
        
        if exists:
            raise exceptions.AuthenticationFailed('Wallet already assigned to a different user')
        
        self.verify(public_address, signature, timestamp, chain)
        return WalletAddress.objects.get_or_create(
            user=user, 
            address=public_address, 
            provider=provider, 
            chain=chain
        )[0]
    
    def verify(self, public_address, signature, timestamp, chain):
        """Cryptographic signature verification"""
        # Timestamp validation (5 minute window)
        cur_timestamp = int(time() * 1000)
        if cur_timestamp - int(timestamp) > 300000:
            raise exceptions.AuthenticationFailed('Signature expired')
        
        # Chain-specific Web3 connection
        if chain == 'celo':
            w3 = Web3(Web3.HTTPProvider(self.celo_url))
        elif chain == 'arbitrum':
            w3 = Web3(Web3.HTTPProvider(self.arbitrum_url))
        else:
            raise exceptions.AuthenticationFailed('Invalid chain')
        
        # Create message that was signed
        message = encode_defunct(text=f'Login to Silvi\nTimestamp: {timestamp}')
        
        try:
            # Recover address from signature
            signerAddress = w3.eth.account.recover_message(message, signature=signature)
        except UnicodeEncodeError as e:
            raise exceptions.AuthenticationFailed('Invalid signature') from e
        
        # Verify the signer matches the claimed address
        if public_address.lower() != signerAddress.lower():
            raise exceptions.AuthenticationFailed('Signature verification failed')
```

### 4. Frontend Authentication Integration
**Path**: `nextjs-frontend/app/api/auth/[...nextauth]/options.ts`
**Purpose**: NextAuth.js configuration for multi-modal auth

```typescript
export const authOptions: NextAuthOptions = {
  session: {
    maxAge: 60 * 60,
    strategy: 'jwt',
  },
  providers: [
    // Traditional credentials
    Credentials({
      id: 'credentials',
      name: 'Email and Password',
      credentials: {
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const payload = {
          username: credentials?.username,
          password: credentials?.password,
        };
        
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}auth/token/`, {
          method: 'POST',
          body: JSON.stringify(payload),
          headers: { 'Content-Type': 'application/json' },
        });
        
        const user = await res.json();
        
        if (res.ok && user) {
          return user;
        }
        
        throw new Error(`Unable to authenticate: ${res.statusText}`);
      },
    }),
    
    // Web3 wallet authentication
    Credentials({
      id: 'wallet-login',
      name: 'Wallet',
      credentials: {
        wallet_address: { label: 'Wallet Address', type: 'text' },
        signature: { label: 'Signature', type: 'text' },
        timestamp: { label: 'Timestamp', type: 'text' },
        chain: { label: 'Chain', type: 'text' },
        wallet_provider: { label: 'Wallet Provider', type: 'text' },
      },
      async authorize(credentials) {
        const payload = {
          wallet_address: credentials?.wallet_address,
          signature: credentials?.signature,
          timestamp: credentials?.timestamp,
          wallet_provider: credentials?.wallet_provider,
          chain: credentials?.chain,
        };
        
        // Try login first, then connect if user doesn't exist
        const user = await connectWallet(payload);
        return user || null;
      },
    }),
    
    // Google OAuth
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  
  callbacks: {
    async signIn({ user, account, profile }) {
      if (account?.provider === "google") {
        const payload = {
          id_token: account.id_token,
          email: profile?.email,
          given_name: profile?.given_name,
          family_name: profile?.family_name,
        };
        
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}auth/google_login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        
        if (!response.ok) return false;
        
        const data = await response.json();
        user.access = data.access;
        user.refresh = data.refresh;
        
        return true;
      }
      return true;
    },
    
    async jwt({ token, user, account }) {
      // Handle token refresh and management
      if (user) {
        return {
          ...token,
          user: user,
          access: user.access,
          refresh: user.refresh,
        };
      } else if (token.exp && token?.exp * 1000 < Date.now()) {
        // Token expired, refresh it
        const newToken = await refreshAccessToken(
          token.access as string,
          token.refresh as string
        );
        
        return {
          ...token,
          access: newToken,
        };
      }
      
      return token;
    },
  },
};
```

## Organizational Structure & User Roles

### Nursery Management System
**Path**: `django-backend/user/models.py`
**Purpose**: Multi-user organizational units for reforestation operations

```python
class Nursery(models.Model):
    """
    Organizational unit representing a tree nursery with multiple users.
    Supports hierarchical management and collaborative operations.
    """
    # Basic information
    name = models.CharField(max_length=256, blank=True, null=True)
    address = models.CharField(max_length=256, blank=True, null=True)
    
    # Multi-user management
    users = models.ManyToManyField(User)  # All users associated with this nursery
    wallet_address = models.ForeignKey('WalletAddress', on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        if self.name is None or self.name == '':
            return 'Unnamed nursery'
        return self.name
    
    @classmethod
    def get_default_nursery(cls, user: User):
        """Get user's default nursery"""
        return cls.objects.filter(users__in=[user]).first()
    
    @classmethod
    def create_default_nursery(cls, user: User):
        """Create default nursery for new users"""
        nursery = cls.objects.create(name=f"{user.username}'s Nursery")
        nursery.users.add(user)
        return nursery
    
    @property
    def total_transfer(self):
        """Calculate total financial transfers for this nursery"""
        return NurseryTransaction.objects.filter(nursery=self).aggregate(
            Sum('transfer')
        )['transfer__sum'] or decimal.Decimal(0)

class NurseryTransaction(models.Model):
    """
    Financial transactions and payments for nursery operations.
    Supports batch processing of multiple logs/claims.
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    nursery = models.ForeignKey('Nursery', on_delete=models.CASCADE, null=True, blank=True)
    goal = models.ForeignKey('core.Goal', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Batch log processing
    log = models.ForeignKey('core.Log', on_delete=models.SET_NULL, null=True, blank=True, 
                           help_text="Deprecated, use logs instead")
    logs = models.ManyToManyField('core.Log', blank=True, related_name='nursery_transactions')
    
    # Transaction status and amounts
    transaction_settled = models.BooleanField(null=True)
    queued = models.BooleanField(default=False)
    credit = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Credit to user account
    transfer = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Transfer to nursery wallet
    
    # Blockchain response
    response = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"nursery: {self.nursery}, goal: {self.goal}, logs: {', '.join([str(log) for log in self.logs.all()])}, credit: {self.credit}, transfer: {self.transfer} settled: {self.transaction_settled}"
```

### Notification System
**Path**: `django-backend/user/models.py`
**Purpose**: Real-time user engagement and onboarding

```python
class Notification(models.Model):
    """
    User notification system with WebSocket integration.
    Handles onboarding flows and real-time updates.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=50)
    title = models.CharField(max_length=100)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Send real-time WebSocket notification
        if is_new:
            from .serializer import NotificationSerializer
            from utils.websockets import send_notification
            
            notification_data = NotificationSerializer(self).data
            send_notification(self.user.id, notification_data)
    
    def __str__(self):
        return f"{self.user.username} - {self.message} - {self.notification_type} - {self.timestamp}"

# Common notification types in the system:
NOTIFICATION_TYPES = {
    'connect_wallet': 'Prompt user to connect blockchain wallet',
    'update_profile': 'Prompt user to complete profile information', 
    'complete_account': 'Prompt user to finalize account setup',
    'claim_approved': 'Notify about approved reforestation claims',
    'payment_received': 'Notify about received payments',
    'tree_verification': 'Notify about tree verification status',
    'campaign_update': 'Updates about campaign progress',
}
```

## Current Limitations & Opportunities for Enhancement

### Missing Features for Advanced Authentication:

1. **Account Abstraction Support**
   - Current wallet auth requires manual signature per login
   - No support for smart contract wallets
   - No gasless transactions for users

2. **Role-Based Access Control (RBAC)**
   - No formal role system beyond nursery membership
   - No granular permissions for different user types
   - No admin/moderator roles for campaign management

3. **Organization Management**
   - Nurseries support multiple users but no hierarchy
   - No formal organization structure
   - No delegation of permissions

4. **Smart Wallet Integration**
   - No support for multi-sig wallets
   - No integration with account abstraction providers
   - No social recovery mechanisms

### Recommended Architecture Enhancements:

```python
# Proposed Role System
class Role(models.Model):
    name = models.CharField(max_length=50)  # 'nursery_manager', 'campaign_admin', 'verifier'
    permissions = models.ManyToManyField('Permission')

class Permission(models.Model):
    codename = models.CharField(max_length=100)  # 'can_verify_trees', 'can_approve_claims'
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)

class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, null=True)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='granted_roles')
    granted_at = models.DateTimeField(auto_now_add=True)

class Organization(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    members = models.ManyToManyField(User, through='OrganizationMembership')
    wallet_addresses = models.ManyToManyField('WalletAddress')

class OrganizationMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_admin = models.BooleanField(default=False)

# Smart Wallet Support
class SmartWallet(models.Model):
    address = models.CharField(max_length=42)
    factory_address = models.CharField(max_length=42)  # Account abstraction factory
    chain = models.CharField(max_length=50, choices=CHAIN_CHOICES)
    owner_addresses = models.ManyToManyField('WalletAddress')  # Multi-sig support
    is_deployed = models.BooleanField(default=False)
    deployment_tx = models.CharField(max_length=66, blank=True, null=True)
```

---

# FRONTEND ARCHITECTURE

## Core TypeScript Interfaces
**Path**: `nextjs-frontend/interfaces/asset.d.ts`
**Purpose**: Type definitions for all reforestation assets

```typescript
// Geographic coordinate system
interface ICoord {
  id: number;
  lat: number;
  lon: number;
}

// Core tree interface
interface ITree {
  id: number;
  point: {
    type: "Point";
    coordinates: [number, number]; // [longitude, latitude]
  };
  species?: {
    id: number;
    species_common_name: string;
    species_scientific_name: string;
  };
  verified: boolean;
  health: 1 | 2 | 3; // Healthy | Unhealthy | Dead
  health_display: string;
  height?: number;
  trunk_diameter?: number;
  goal?: number;
}

// GeoJSON structure for trees
interface TreeFeatureCollection {
  type: "FeatureCollection";
  features: TreeFeature[];
}

interface TreeFeature {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: ITree;
}

// Nursery structures
interface ISeedbed {
  id: number;
  polygon?: {
    type: "MultiPolygon";
    coordinates: number[][][][];
  };
  species?: ISpecies;
  capacity: number;
  current_count: number;
  sowing_date?: string;
  germination_rate?: number;
  goal?: number;
}

interface IPottedbed {
  id: number;
  polygon?: {
    type: "MultiPolygon"; 
    coordinates: number[][][][];
  };
  species?: ISpecies;
  capacity: number;
  current_count: number;
  potting_date?: string;
  source_seed_bed?: number;
  goal?: number;
}

// Campaign and project structures
interface ICampaign {
  id: number;
  title: string;
  description: string;
  countries?: string[];
  bioregions?: string[];
  ecoregions?: string[];
  goal?: IGoal;
  zone?: IZone;
  cover_image?: IImage;
  partners?: ICampaignPartner[];
  instructions?: string;
  instructions_video_url?: string;
}

interface IGoal {
  id: number;
  target: number;
  start_date: string;
  end_date: string;
  active: boolean;
  trees_planted?: number;
  completion_percentage?: number;
  chain: 'celo' | 'arbitrum';
  pool_address?: string;
}

// Geographic zones
interface IZone {
  id: number;
  multipolygon: {
    type: "MultiPolygon";
    coordinates: number[][][][];
  };
  name?: string;
  area?: number;
  goal?: IGoal;
}
```

## Map Component - Core Visualization
**Path**: `nextjs-frontend/components/trees_and_maps/MapboxMap.tsx`
**Purpose**: Main map interface for visualizing reforestation data

```typescript
const MapboxMap: React.FC<MapboxMapProps> = ({
  initialOptions = {},
  onMapLoaded,
  onMapRemoved,
}) => {
  // Map state management
  const [map, setMap] = useState<mapboxgl.Map | null>(null);
  const [currentZoom, setCurrentZoom] = useState<number>(2);
  const [currentGeohash, setCurrentGeohash] = useState<string>("");
  
  // Authentication
  const { data: session } = useSession();
  const authToken = session?.accessToken as string;

  // Data fetching with geohash-based loading
  const { data: geohashTreeData, isLoading: isGeohashTreeDataLoading } = useQuery({
    queryKey: ["treeListByGeohash", currentGeohash, authToken],
    queryFn: () => fetchTreeListByGeohash(currentGeohash, authToken),
    enabled: !!authToken && !!currentGeohash,
    staleTime: 30000, // Cache for 30 seconds
  });

  // Use geohash data if available, fallback to regular tree data
  const activeTreeData = currentGeohash && geohashTreeData ? geohashTreeData : treeData;

  // Tree categorization for different visualizations
  useEffect(() => {
    function loadTreeData() {
      if (!map || !treeData?.features?.length) return;

      // Split features into different categories
      const healthyTrees = {
        type: "FeatureCollection",
        features: treeData.features.filter(
          (tree) => tree.properties?.verified && tree.properties.health === 1
        ),
      };

      const deadTrees = {
        type: "FeatureCollection", 
        features: treeData.features.filter(
          (tree) => tree.properties.verified && tree.properties.health === 3
        ),
      };

      const unverifiedTrees = {
        type: "FeatureCollection",
        features: treeData.features.filter(
          (tree) => !tree.properties.verified
        ),
      };

      // Add clustered sources for each tree type
      map.addSource(`healthy_trees_${uniqueTreeId}`, {
        type: "geojson",
        data: healthyTrees,
        cluster: true,
        clusterMaxZoom: 14,
        clusterRadius: 50,
      });

      // Add visual layers with health-based styling
      map.addLayer({
        id: `healthy_clusters_${uniqueTreeId}`,
        type: "circle",
        source: `healthy_trees_${uniqueTreeId}`,
        filter: ["has", "point_count"],
        paint: {
          "circle-color": "#75e33a", // Green for healthy
          "circle-radius": [
            "step",
            ["get", "point_count"],
            20, 10, 30, 100, 40,
          ],
        },
      });

      // Similar layers for dead (gray) and unverified (white) trees
    }

    loadTreeData();
  }, [map, treeData]);

  // Geohash calculation based on viewport
  useEffect(() => {
    if (!map) return;

    const updateGeohash = () => {
      const bounds = map.getBounds();
      const zoom = map.getZoom();
      setCurrentZoom(zoom);
      
      const newGeohash = getViewportCenterGeohash(bounds, zoom);
      
      if (hasGeohashChanged(newGeohash, currentGeohash)) {
        setCurrentGeohash(newGeohash);
      }
    };

    map.on('moveend', updateGeohash);
    map.on('zoomend', updateGeohash);
    
    return () => {
      map.off('moveend', updateGeohash);
      map.off('zoomend', updateGeohash);
    };
  }, [map, currentGeohash]);

  return (
    <div ref={mapContainer} className="map-container w-full h-full" />
  );
};
```

## Data Fetching Layer
**Path**: `nextjs-frontend/app/actions/assetQueries.ts`
**Purpose**: API integration for reforestation data

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/';

// Authenticated API calls
export const fetchWithAuth = async (url: string, authToken?: string) => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  
  const response = await fetch(url, { headers });
  
  if (!response.ok) {
    throw new Error('Network response was not ok');
  }
  
  return response.json();
};

// Core data fetching functions
export const fetchTreeList = async (authToken?: string): Promise<TreeFeatureCollection> => {
  return fetchWithAuth(`${API_URL}core/tree_list/`, authToken);
};

export const fetchTreeListByGeohash = async (geohash: string, authToken?: string): Promise<TreeFeatureCollection> => {
  return fetchWithAuth(`${API_URL}core/tree_list/?geohash=${geohash}`, authToken);
};

export const fetchSeedbedList = async (authToken?: string): Promise<SeedbedFeatureCollection> => {
  return fetchWithAuth(`${API_URL}core/seed_bed_list`, authToken);
};

export const fetchPottedbedList = async (authToken?: string): Promise<PottedbedFeatureCollection> => {
  return fetchWithAuth(`${API_URL}core/potted_bed_list`, authToken);
};

export const fetchCampaignList = async (authToken?: string): Promise<ICampaign[]> => {
  return fetchWithAuth(`${API_URL}core/campaign_list/`, authToken);
};

export const fetchZoneList = async (authToken?: string): Promise<ZoneFeatureCollection> => {
  return fetchWithAuth(`${API_URL}core/zone_list/`, authToken);
};
```

---

# BLOCKCHAIN INTEGRATION & VERIFICATION

## Ethereum Attestation Service (EAS) Integration
**Path**: `django-backend/utils/eas.py`
**Purpose**: Create verifiable attestations for reforestation claims

```python
from eth_account import Account
from web3 import Web3
import json

class EASService:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URL))
        self.account = Account.from_key(settings.WALLET_PRIVATE_KEY)
        
    def create_tree_attestation(self, tree_id, claim_type, evidence_hash):
        """Create an attestation for a tree planting claim"""
        schema_uid = "0x..." # Tree planting schema
        
        attestation_data = {
            "tree_id": tree_id,
            "claim_type": claim_type,
            "evidence_ipfs_hash": evidence_hash,
            "timestamp": int(time.time()),
            "location": tree.point.coords if tree.point else None,
            "species": tree.species.species_scientific_name if tree.species else None
        }
        
        # Encode data according to schema
        encoded_data = self.encode_attestation_data(attestation_data)
        
        # Create attestation transaction
        tx = self.eas_contract.functions.attest({
            'schema': schema_uid,
            'data': {
                'recipient': tree.user.wallet_address,
                'expirationTime': 0,  # No expiration
                'revocable': True,
                'refUID': "0x0",
                'data': encoded_data,
                'value': 0
            }
        }).build_transaction({
            'from': self.account.address,
            'gas': 200000,
            'gasPrice': self.w3.toWei('20', 'gwei'),
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })
        
        # Sign and send transaction
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        return tx_hash.hex()
```

## IPFS Integration for Evidence Storage
**Path**: `django-backend/utils/ipfs.py`
**Purpose**: Decentralized storage of images and documents

```python
import ipfshttpclient
import json
import base64

class IPFSService:
    def __init__(self):
        self.client = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5001')
        
    def upload_tree_evidence(self, tree_log):
        """Upload tree evidence package to IPFS"""
        evidence_package = {
            "tree_id": tree_log.tree.id,
            "timestamp": tree_log.timestamp.isoformat(),
            "location": {
                "latitude": tree_log.point.y if tree_log.point else None,
                "longitude": tree_log.point.x if tree_log.point else None
            },
            "claim_type": tree_log.get_claim_type_display(),
            "notes": tree_log.notes,
            "measurements": {
                "height": tree_log.height,
                "trunk_diameter": tree_log.tree.trunk_diameter if tree_log.tree else None
            },
            "species": {
                "common_name": tree_log.tree.species.species_common_name if tree_log.tree and tree_log.tree.species else None,
                "scientific_name": tree_log.tree.species.species_scientific_name if tree_log.tree and tree_log.tree.species else None
            },
            "images": [],
            "user": tree_log.user.username if tree_log.user else None
        }
        
        # Add images to package
        for image in tree_log.images.all():
            if image.base64_image_data:
                # Upload individual image
                image_hash = self.client.add_bytes(
                    base64.b64decode(image.base64_image_data)
                )
                evidence_package["images"].append({
                    "ipfs_hash": image_hash,
                    "order": image.order,
                    "timestamp": image.timestamp.isoformat()
                })
        
        # Upload complete evidence package
        package_json = json.dumps(evidence_package, indent=2)
        package_hash = self.client.add_str(package_json)
        
        return package_hash
```

---

# KEY BUSINESS LOGIC PATTERNS

## Reforestation Lifecycle Management

The system tracks the complete lifecycle of reforestation:

1. **Seed Collection & Sowing** → `SeedBed` creation with `Log` entries
2. **Germination Tracking** → Updates to `SeedBed.current_count` and `germination_rate`
3. **Transplanting to Pots** → `PottedBed` creation linked to source `SeedBed`
4. **Sapling Growth** → Regular `Log` entries with height measurements
5. **Field Planting** → `Tree` creation with `source_potting_bed` reference
6. **Ongoing Monitoring** → Periodic `Log` entries with health assessments
7. **Verification & Claims** → `tree.verified = True` triggers carbon credit eligibility

## Carbon Credit Generation Logic

```python
def calculate_carbon_credits(tree):
    """Calculate potential carbon credits for a tree"""
    if not tree.verified or tree.health != 1:  # Only healthy, verified trees
        return 0
    
    # Base calculation factors
    age_years = (timezone.now() - tree.created_date).days / 365
    species_factor = tree.species.carbon_sequestration_rate or 1.0
    health_factor = 1.0 if tree.health == 1 else 0.5
    
    # Estimate annual CO2 sequestration (kg/year)
    annual_sequestration = species_factor * health_factor
    total_sequestration = annual_sequestration * age_years
    
    # Convert to carbon credits (1 credit = 1 tonne CO2)
    credits = total_sequestration / 1000
    
    return max(0, credits)
```

## Permission & Access Control Patterns

```python
# Tree access control
def user_can_modify_tree(user, tree):
    """Determine if user can modify a tree"""
    # Tree creator can always modify
    if tree.logs.filter(user=user, event=2).exists():  # Tree registration event
        return True
    
    # Nursery managers can modify trees from their nurseries
    if tree.source_potting_bed and tree.source_potting_bed.nursery:
        if user in tree.source_potting_bed.nursery.managers.all():
            return True
    
    # Goal administrators can modify trees in their goals
    if tree.goal and hasattr(tree.goal, 'administrators'):
        if user in tree.goal.administrators.all():
            return True
    
    return False

# Campaign participation logic
def user_can_participate_in_campaign(user, campaign):
    """Check if user can participate in a campaign"""
    # Geographic restrictions
    if campaign.countries and user.profile.country not in campaign.countries:
        return False
    
    # Verification requirements
    if campaign.requires_verification and not user.profile.is_verified:
        return False
    
    # Capacity limits
    if campaign.max_participants:
        current_participants = Log.objects.filter(
            goal=campaign.goal
        ).values('user').distinct().count()
        
        if current_participants >= campaign.max_participants:
            return False
    
    return True
```

---

# COMPREHENSIVE BLOCKCHAIN INTEGRATION DETAILS

## Multi-Chain Smart Contract Architecture

### Contract Addresses & Networks
```python
# Celo Network
CELO_MAINNET_RPC = "https://forno.celo.org"
CELO_TESTNET_RPC = "https://alfajores-forno.celo-testnet.org"
CELO_EAS_ADDRESS = "0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92"  # Mainnet
CELO_POOLFACTORY_CONTRACT_ADDRESS = "0x4e51E761707d11012f51E99B266CD195cEBbFa04"  # Mainnet
CELO_STRATEGY_CONTRACT_ADDRESS = "0x62AdD3384D8185213b6d301B78AaADcD45BA87e9"  # Mainnet

# Arbitrum Network  
ARBITRUM_MAINNET_RPC = "https://arbitrum-one-rpc.publicnode.com"
ARBITRUM_TESTNET_RPC = "https://sepolia-rollup.arbitrum.io/rpc"
ARBITRUM_EAS_ADDRESS = "0xbD75f629A22Dc1ceD33dDA0b68c546A1c035c458"  # Mainnet
ARBITRUM_POOLFACTORY_CONTRACT_ADDRESS = "0xe647b7Ec1841bf32a291Bf7392bcEc2A5Ab7A542"  # Mainnet
ARBITRUM_STRATEGY_CONTRACT_ADDRESS = "0x848811CAa9d39581Cb31185e8367EcE1E5F0a779"  # Mainnet
```

## EAS Attestation System - Complete Implementation

### Automatic Attestation Creation
**Path**: `django-backend/core/models.py` - Log.attest_creation()

```python
def attest_creation(self):
    """Automatically attest claim creation to EAS when logs are created"""
    requirements = [self.goal]
    
    if all(requirements):
        import core.serializer as core_serializer
        
        # Serialize the complete claim data
        serializer = core_serializer.LogMetadataSerializer(self)
        json_data = json.dumps(serializer.data)
        
        # Create EAS attestation record
        attestation = basemodels.EasAttestation(
            subject_id=str(self.pk),
            event_type="claim:created",
            json_data=json_data,
            chain=self.goal.chain,
            recipient=self.user.profile.related_wallet_address if hasattr(self.user, 'profile') else None
        )
        attestation.save()  # This triggers the on-chain attestation
```

### EAS Event Types & Schemas
```python
EAS_EVENT_TYPE_CHOICES = (
    ('goal:goal_configured', 'Goal Configured'),      # When reforestation goal is set up
    ('goal:pool_deployed', 'Pool Deployed'),          # When funding pool is deployed
    ('claim:created', 'Claim Created'),               # When user submits reforestation claim
    ('claim:settled', 'Claim Settled'),               # When claim is verified and approved
    ('milestones:summary', 'Milestones Summary'),     # Progress milestones (25%, 50%, 75%)
    ('milestones:completed', 'Milestones Completed'), # When goal is 100% complete
)

# Schema Structure: [subject_id, event_type, json_data]
# - subject_id: ID of the tree, goal, or claim being attested
# - event_type: Type of event from EAS_EVENT_TYPE_CHOICES
# - json_data: Serialized metadata (coordinates, species, measurements, etc.)
```

## Allo Protocol Pool Management

### Complete Pool Lifecycle
1. **Goal Creation**: Reforestation goal defined with target trees
2. **Pool Deployment**: Allo pool deployed with custom Silvi strategy
3. **Pool Funding**: Funders deposit tokens (USDC, cUSD) into pool
4. **Claim Processing**: Users submit claims, automatically attested via EAS
5. **Verification**: Claims verified by administrators
6. **Payment Distribution**: Verified claims trigger automatic payments from pool
7. **Pool Monitoring**: Track funding, distributions, and remaining balance

### Pool Balance & Analytics
```python
def get_pool_balance(pool_address, token_address, chain, decimals):
    """Get current token balance in a reforestation pool"""
    token_contract = connection.eth.contract(address=token_address, abi=ERC20_ABI)
    balance = token_contract.functions.balanceOf(pool_address).call()
    return balance / pow(10, decimals)

def get_total_funded_amount(pool_address, chain, decimals):
    """Get total amount ever funded into the pool"""
    pool_instance = connection.eth.contract(address=pool_address, abi=STRATEGY_ABI)
    total_funded = pool_instance.functions.getTotalFunded().call()
    return total_funded / pow(10, decimals)

def get_total_deployed_amount(pool_address, chain, decimals):
    """Get total amount distributed from the pool"""
    pool_instance = connection.eth.contract(address=pool_address, abi=STRATEGY_ABI)
    total_distributed = pool_instance.functions.getTotalDistributed().call()
    return total_distributed / pow(10, decimals)
```

## GoodCollective NFT Rewards

### Pool Configuration Model
```python
class Pool(models.Model):
    """GoodCollective pool for NFT rewards"""
    name = models.CharField(max_length=256)
    contract_address = models.CharField(max_length=50, unique=True)
    nft_type = models.IntegerField()
    version = models.IntegerField()
    
    # Rate limiting for rewards
    reward_limit_per_month = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    reward_limit_for_member_per_month = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    reward_limit_for_member_per_day = models.DecimalField(max_digits=10, decimal_places=3, default=1)

class PoolEvent(models.Model):
    """Maps claim types to specific NFT rewards"""
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    claim_type = models.IntegerField(choices=CLAIM_TYPE_CHOICES, default=0)
    event_type = models.IntegerField()
    reward = models.DecimalField(max_digits=6, decimal_places=3)
    
    class Meta:
        unique_together = ["pool", "event_type"]
```

## Frontend Web3 Integration

### Wallet Connection System
**Path**: `nextjs-frontend/lib/new-provider.tsx`

```typescript
// Multi-chain configuration
const chains = [celo, arbitrum] as const;

// Wallet providers
const config = getDefaultConfig({
  appName: 'Silvi',
  projectId: process.env.NEXT_PUBLIC_WALLET_CONNECT_PROJECT_ID!,
  chains,
  ssr: true,
});

// Complete provider setup with Web3 integration
function NewProviders({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <ViewportProvider>
        <AppDataProvider>
          <AlertProvider>
            <NotificationsProvider>
              <QueryClientProvider client={queryClient}>
                <WagmiConfig config={config}>
                  <RainbowKitProvider>
                    <GoogleOAuthProvider clientId={process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID!}>
                      <CameraTriggerProvider>
                        {children}
                      </CameraTriggerProvider>
                    </GoogleOAuthProvider>
                  </RainbowKitProvider>
                </WagmiConfig>
              </QueryClientProvider>
            </NotificationsProvider>
          </AlertProvider>
        </AppDataProvider>
      </ViewportProvider>
    </SessionProvider>
  );
}
```

---

# BLOCKCHAIN INTEGRATION SUMMARY

## ✅ **Complete On-Chain Functionality**

1. **EAS Attestations**: Immutable verification of all reforestation activities
2. **Allo Pool Deployment**: Funding pools for each reforestation goal
3. **Strategy Contracts**: Custom verification logic before payments
4. **Automated Payments**: Verified claims trigger automatic distributions
5. **NFT Rewards**: Achievement NFTs via GoodCollective integration
6. **Multi-Chain Support**: Full Celo and Arbitrum integration
7. **Schema Management**: Structured attestation data
8. **Payment Triggers**: Complete flow from claim to settlement
9. **Pool Analytics**: Funding, distribution, and balance tracking
10. **Error Handling**: Comprehensive blockchain error management

## 🚀 **Architecture for Advanced Features**

The current blockchain architecture provides a solid foundation for implementing:
- **Account Abstraction**: Smart contract wallets for gasless transactions
- **Cross-Chain Operations**: Bridge assets between Celo and Arbitrum
- **DeFi Integration**: Yield generation on pool funds
- **Carbon Credit Tokenization**: ERC-1155 tokens for verified carbon sequestration
- **DAO Governance**: Token-based voting for platform decisions

---

# DATA SCHEMAS & STANDARDS IMPLEMENTATION

## IPFS Integration - Complete Implementation
**Path**: `django-backend/utils/ipfs.py`

The system uses **Lighthouse API** for IPFS operations:
- **JSON Storage**: `pin_json()` for metadata and evidence packages
- **File Storage**: `pin_file()` for images, videos, documents  
- **Data Retrieval**: `read_cid_json()` for accessing stored data
- **Abstract Model**: `IpfsJsonModel` base class for IPFS-enabled models

## STAC API - Geospatial Data Catalog
**Path**: `django-backend/core/stac_views.py`

Complete STAC (SpatioTemporal Asset Catalog) implementation:
- **Root Catalog**: Organized into raster, vector, administrative, evidence subcatalogs
- **Collections**: Trees, seed beds, potted beds, campaigns, projects, goals
- **Items**: Individual assets with comprehensive metadata
- **Tile Service**: XYZ tile endpoints for raster data visualization

## JSON Schema Generation
**Path**: `django-backend/core/serializer.py`

**SerializerWithSchema** class auto-generates JSON schemas for:
- All API endpoints and responses
- Field type mapping (Django → JSON Schema)
- Validation rules and constraints
- Nested object structures
- Choice field enumerations

## Evidence Package Schemas

### Tree Evidence Structure (IPFS-stored)
```json
{
  "tree_id": "integer",
  "timestamp": "ISO datetime",
  "location": {"latitude": "number", "longitude": "number"},
  "claim_type": "string",
  "measurements": {"height": "number", "trunk_diameter": "number"},
  "species": {"common_name": "string", "scientific_name": "string"},
  "images": [{"ipfs_hash": "string", "order": "integer"}],
  "user": "string",
  "verification_status": "enum"
}
```

This comprehensive audit now includes ALL functionality: blockchain integration, IPFS schemas, STAC implementation, JSON schema generation, and complete data standards.
