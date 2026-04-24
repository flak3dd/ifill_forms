import random
import string
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from playwright.async_api import BrowserContext


class OSType(Enum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


class BrowserType(Enum):
    CHROME = "chrome"
    FIREFOX = "firefox"
    SAFARI = "safari"
    EDGE = "edge"


@dataclass
class BrowserProfile:
    """A correlated browser fingerprint profile for consistent spoofing."""
    os_type: OSType
    browser_type: BrowserType
    user_agent: str
    platform: str
    vendor: str
    viewport: Dict[str, int]
    screen: Dict[str, int]
    hardware_concurrency: int
    device_memory: int
    max_touch_points: int
    locale: str
    timezone: str
    geolocation: Dict[str, float]
    color_scheme: str = "light"
    is_mobile: bool = False


# Expanded User Agents with version variety
USER_AGENTS: Dict[Tuple[OSType, BrowserType], List[str]] = {
    (OSType.WINDOWS, BrowserType.CHROME): [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    ],
    (OSType.WINDOWS, BrowserType.FIREFOX): [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    ],
    (OSType.WINDOWS, BrowserType.EDGE): [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    ],
    (OSType.MACOS, BrowserType.CHROME): [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ],
    (OSType.MACOS, BrowserType.SAFARI): [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    ],
    (OSType.LINUX, BrowserType.CHROME): [
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    ],
    (OSType.LINUX, BrowserType.FIREFOX): [
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ],
}

# OS-specific platform strings
PLATFORM_STRINGS: Dict[OSType, str] = {
    OSType.WINDOWS: "Win32",
    OSType.MACOS: "MacIntel",
    OSType.LINUX: "Linux x86_64",
}

# Browser-specific vendor strings
VENDOR_STRINGS: Dict[BrowserType, str] = {
    BrowserType.CHROME: "Google Inc.",
    BrowserType.FIREFOX: "",
    BrowserType.SAFARI: "Apple Computer, Inc.",
    BrowserType.EDGE: "Google Inc.",
}

# Viewport presets correlated with OS
VIEWPORT_PRESETS: Dict[OSType, List[Dict[str, int]]] = {
    OSType.WINDOWS: [
        {"width": 1536, "height": 864},  # 125% scaling at 1920x1080
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 810},
        {"width": 1280, "height": 720},
    ],
    OSType.MACOS: [
        {"width": 1440, "height": 900},
        {"width": 1680, "height": 1050},
        {"width": 2560, "height": 1440},
        {"width": 1920, "height": 1080},
        {"width": 1512, "height": 982},  # M1/M2 default
    ],
    OSType.LINUX: [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1536, "height": 864},
        {"width": 2560, "height": 1440},
    ],
}

# Hardware specs by OS (realistic ranges)
HARDWARE_SPECS: Dict[OSType, Dict[str, List[int]]] = {
    OSType.WINDOWS: {
        "cores": [4, 6, 8, 12, 16],
        "memory": [4, 8, 16, 32],
    },
    OSType.MACOS: {
        "cores": [8, 10, 12],
        "memory": [8, 16, 32],
    },
    OSType.LINUX: {
        "cores": [4, 8, 16],
        "memory": [8, 16, 32, 64],
    },
}

LOCALES: Dict[OSType, List[str]] = {
    OSType.WINDOWS: ["en-US", "en-GB", "en-CA", "es-US", "fr-CA"],
    OSType.MACOS: ["en-US", "en-GB", "en-AU"],
    OSType.LINUX: ["en-US", "en-GB", "de-DE", "fr-FR"],
}

TIMEZONES: List[Dict[str, str]] = [
    {"id": "America/New_York", "locale": "en-US"},
    {"id": "America/Chicago", "locale": "en-US"},
    {"id": "America/Denver", "locale": "en-US"},
    {"id": "America/Los_Angeles", "locale": "en-US"},
    {"id": "America/Toronto", "locale": "en-CA"},
    {"id": "Europe/London", "locale": "en-GB"},
    {"id": "Europe/Berlin", "locale": "de-DE"},
    {"id": "Europe/Paris", "locale": "fr-FR"},
    {"id": "Australia/Sydney", "locale": "en-AU"},
]

GEO_LOCATIONS: Dict[str, List[Dict[str, float]]] = {
    "America/New_York": [
        {"latitude": 40.7128, "longitude": -74.0060},
        {"latitude": 40.7580, "longitude": -73.9855},
    ],
    "America/Chicago": [
        {"latitude": 41.8781, "longitude": -87.6298},
    ],
    "America/Denver": [
        {"latitude": 39.7392, "longitude": -104.9903},
    ],
    "America/Los_Angeles": [
        {"latitude": 34.0522, "longitude": -118.2437},
        {"latitude": 33.9425, "longitude": -118.4081},
    ],
    "America/Toronto": [
        {"latitude": 43.6532, "longitude": -79.3832},
    ],
    "Europe/London": [
        {"latitude": 51.5074, "longitude": -0.1278},
        {"latitude": 51.5099, "longitude": -0.1180},
    ],
    "Europe/Berlin": [
        {"latitude": 52.5200, "longitude": 13.4050},
    ],
    "Europe/Paris": [
        {"latitude": 48.8566, "longitude": 2.3522},
    ],
    "Australia/Sydney": [
        {"latitude": -33.8688, "longitude": 151.2093},
    ],
}

# Realistic HTTP headers
DEFAULT_HEADERS: Dict[str, str] = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Comprehensive anti-detection script
ANTI_BOT_INIT_SCRIPT = """
(() => {
  'use strict';

  // Store configuration injected by Python
  const config = window.__STEALTH_CONFIG__ || {};

  // ========== NAVIGATOR PROPERTIES ==========

  // Webdriver flag
  Object.defineProperty(navigator, 'webdriver', {
    get: () => false,
    configurable: true,
  });

  // Languages
  const languages = config.languages || ['en-US', 'en'];
  Object.defineProperty(navigator, 'languages', {
    get: () => languages,
    configurable: true,
  });

  // Platform
  const platform = config.platform || 'Win32';
  Object.defineProperty(navigator, 'platform', {
    get: () => platform,
    configurable: true,
  });

  // Vendor
  const vendor = config.vendor || 'Google Inc.';
  Object.defineProperty(navigator, 'vendor', {
    get: () => vendor,
    configurable: true,
  });

  // Hardware concurrency
  const cores = config.hardwareConcurrency || 8;
  Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => cores,
    configurable: true,
  });

  // Device memory
  const memory = config.deviceMemory || 8;
  if (navigator.deviceMemory !== undefined) {
    Object.defineProperty(navigator, 'deviceMemory', {
      get: () => memory,
      configurable: true,
    });
  }

  // Max touch points
  const touchPoints = config.maxTouchPoints || 0;
  Object.defineProperty(navigator, 'maxTouchPoints', {
    get: () => touchPoints,
    configurable: true,
  });

  // Connection
  if (!navigator.connection) {
    Object.defineProperty(navigator, 'connection', {
      get: () => ({
        effectiveType: '4g',
        rtt: 50,
        downlink: 10,
        saveData: false,
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => true,
      }),
      configurable: true,
    });
  }

  // ========== PLUGINS (Chrome-style) ==========
  
  const createPlugin = (name, filename, description) => {
    const plugin = {
      name: name,
      filename: filename,
      description: description,
      length: 1,
      item: (i) => plugin,
      namedItem: (name) => plugin,
    };
    return plugin;
  };

  const plugins = [
    createPlugin('PDF Plugin', 'internal-pdf-viewer', 'Portable Document Format'),
    createPlugin('Chrome PDF Plugin', 'internal-pdf-viewer', 'Portable Document Format'),
    createPlugin('Chromium PDF Plugin', 'internal-pdf-viewer', 'Portable Document Format'),
    createPlugin('Microsoft Edge PDF Plugin', 'internal-pdf-viewer', 'Portable Document Format'),
    createPlugin('WebKit built-in PDF', 'internal-pdf-viewer', 'Portable Document Format'),
  ];

  const pluginArray = Object.create(PluginArray.prototype);
  plugins.forEach((p, i) => {
    Object.defineProperty(pluginArray, i, { get: () => p, configurable: true });
    Object.defineProperty(pluginArray, p.name, { get: () => p, configurable: true });
  });
  Object.defineProperty(pluginArray, 'length', { get: () => plugins.length, configurable: true });
  Object.defineProperty(pluginArray, 'item', {
    value: (i) => pluginArray[i] || null,
    configurable: true,
  });
  Object.defineProperty(pluginArray, 'namedItem', {
    value: (name) => pluginArray[name] || null,
    configurable: true,
  });
  Object.defineProperty(pluginArray, 'refresh', {
    value: () => {},
    configurable: true,
  });

  Object.defineProperty(navigator, 'plugins', {
    get: () => pluginArray,
    configurable: true,
  });

  // MimeTypes
  const mimeTypes = [
    { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
    { type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
  ];

  const mimeTypeArray = Object.create(MimeTypeArray.prototype);
  mimeTypes.forEach((m, i) => {
    Object.defineProperty(mimeTypeArray, i, { get: () => m, configurable: true });
    Object.defineProperty(mimeTypeArray, m.type, { get: () => m, configurable: true });
  });
  Object.defineProperty(mimeTypeArray, 'length', { get: () => mimeTypes.length, configurable: true });

  Object.defineProperty(navigator, 'mimeTypes', {
    get: () => mimeTypeArray,
    configurable: true,
  });

  // ========== CHROME OBJECT ==========

  if (!window.chrome) {
    window.chrome = {};
  }

  if (!window.chrome.runtime) {
    // Prevent "Extension context invalidated" errors
    window.chrome.runtime = {
      connect: function() {
        throw new Error('Extension context invalidated');
      },
      sendMessage: function() {
        throw new Error('Extension context invalidated');
      },
      onMessage: {
        addListener: function() {},
        removeListener: function() {},
      },
      id: undefined,
    };
  }

  if (!window.chrome.loadTimes) {
    const loadTime = Date.now() / 1000;
    window.chrome.loadTimes = () => ({
      requestTime: loadTime,
      startLoadTime: loadTime,
      commitLoadTime: loadTime + 0.001,
      finishDocumentLoadTime: loadTime + 0.05,
      finishLoadTime: loadTime + 0.1,
      firstPaintTime: loadTime + 0.03,
      firstPaintAfterLoadTime: 0,
      navigationType: 'Other',
      wasFetchedViaSpdy: true,
      wasNpnNegotiated: true,
      npnNegotiatedProtocol: 'h2',
      wasAlternateProtocolAvailable: false,
      connectionInfo: 'h2',
    });
  }

  if (!window.chrome.csi) {
    window.chrome.csi = () => ({
      onloadT: Date.now(),
      pageT: Math.random() * 100 + 50,
      startE: Date.now(),
      tran: 15,
    });
  }

  // ========== PERMISSIONS ==========

  const permissions = window.navigator.permissions;
  if (permissions && permissions.query) {
    const originalQuery = permissions.query.bind(permissions);
    permissions.query = (parameters) => {
      if (parameters.name === 'notifications') {
        return Promise.resolve({ 
          state: Notification.permission,
          onchange: null,
        });
      }
      if (parameters.name === 'geolocation') {
        return Promise.resolve({ state: 'granted', onchange: null });
      }
      if (parameters.name === 'camera' || parameters.name === 'microphone') {
        return Promise.resolve({ state: 'prompt', onchange: null });
      }
      return originalQuery(parameters);
    };
  }

  // ========== SCREEN PROPERTIES ==========

  const viewportWidth = config.viewportWidth || window.innerWidth;
  const viewportHeight = config.viewportHeight || window.innerHeight;
  
  // Calculate realistic screen dimensions (usually larger than viewport)
  const screenScale = config.screenScale || 1.25;
  const screenWidth = Math.round(viewportWidth * screenScale);
  const screenHeight = Math.round(viewportHeight * screenScale);

  const screenProps = {
    width: screenWidth,
    height: screenHeight,
    availWidth: screenWidth,
    availHeight: screenHeight - 40, // Taskbar
    colorDepth: 24,
    pixelDepth: 24,
    orientation: {
      type: 'landscape-primary',
      angle: 0,
    },
  };

  if (window.screen) {
    Object.keys(screenProps).forEach(key => {
      if (typeof screenProps[key] === 'object') {
        Object.defineProperty(window.screen, key, {
          get: () => screenProps[key],
          configurable: true,
        });
      } else {
        Object.defineProperty(window.screen, key, {
          get: () => screenProps[key],
          configurable: true,
        });
      }
    });
  }

  // Window dimensions
  Object.defineProperty(window, 'outerWidth', {
    get: () => viewportWidth,
    configurable: true,
  });
  Object.defineProperty(window, 'outerHeight', {
    get: () => viewportHeight + 80, // Browser chrome
    configurable: true,
  });
  Object.defineProperty(window, 'devicePixelRatio', {
    get: () => 1,
    configurable: true,
  });

  // ========== CANVAS FINGERPRINT PROTECTION ==========

  const addNoise = (value, variance = 0.0001) => {
    return value + (Math.random() - 0.5) * variance;
  };

  const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
  HTMLCanvasElement.prototype.toDataURL = function(type, quality) {
    if (type === 'image/png' || type === undefined) {
      const context = this.getContext('2d');
      if (context) {
        const imageData = context.getImageData(0, 0, this.width, this.height);
        for (let i = 0; i < imageData.data.length; i += 4) {
          if (imageData.data[i] > 0) { // Only modify non-transparent pixels
            imageData.data[i] = addNoise(imageData.data[i], 2);       // R
            imageData.data[i + 1] = addNoise(imageData.data[i + 1], 2); // G
            imageData.data[i + 2] = addNoise(imageData.data[i + 2], 2); // B
          }
        }
        context.putImageData(imageData, 0, 0);
      }
    }
    return originalToDataURL.call(this, type, quality);
  };

  // ========== WEBGL FINGERPRINT PROTECTION ==========

  const getParameterProxyHandler = {
    apply: function(target, thisArg, args) {
      const param = args[0];
      const result = target.apply(thisArg, args);
      
      // Add slight noise to renderer string
      if (param === 0x1F01) { // RENDERER
        return result.replace(/\\d+\\.\\d+/, (match) => {
          const parts = match.split('.');
          parts[parts.length - 1] = String(parseInt(parts[parts.length - 1]) + Math.floor(Math.random() * 10));
          return parts.join('.');
        });
      }
      return result;
    }
  };

  const getExtensionProxyHandler = {
    apply: function(target, thisArg, args) {
      const extension = target.apply(thisArg, args);
      if (extension && extension.getParameter) {
        extension.getParameter = new Proxy(extension.getParameter, getParameterProxyHandler);
      }
      return extension;
    }
  };

  const originalGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function(type, attributes) {
    const context = originalGetContext.call(this, type, attributes);
    if (type === 'webgl' || type === 'webgl2' || type === 'experimental-webgl') {
      if (context && context.getParameter) {
        context.getParameter = new Proxy(context.getParameter, getParameterProxyHandler);
      }
      if (context && context.getExtension) {
        context.getExtension = new Proxy(context.getExtension, getExtensionProxyHandler);
      }
    }
    return context;
  };

  // ========== AUDIO FINGERPRINT PROTECTION ==========

  const originalCreateOscillator = AudioContext.prototype.createOscillator;
  AudioContext.prototype.createOscillator = function() {
    const oscillator = originalCreateOscillator.call(this);
    const originalFrequency = Object.getOwnPropertyDescriptor(OscillatorNode.prototype, 'frequency');
    
    if (originalFrequency && originalFrequency.get) {
      Object.defineProperty(oscillator, 'frequency', {
        get: function() {
          const freq = originalFrequency.get.call(this);
          const noisyFreq = Object.create(freq);
          noisyFreq.value = freq.value + (Math.random() - 0.5) * 0.01;
          return noisyFreq;
        },
        configurable: true,
      });
    }
    return oscillator;
  };

  // ========== WEBRTC LEAK PREVENTION ==========

  if (window.RTCPeerConnection) {
    const originalGetLocalStreams = RTCPeerConnection.prototype.getLocalStreams;
    RTCPeerConnection.prototype.getLocalStreams = function() {
      return [];
    };
    
    const originalGetReceivers = RTCPeerConnection.prototype.getReceivers;
    RTCPeerConnection.prototype.getReceivers = function() {
      const receivers = originalGetReceivers.call(this);
      return receivers.map(r => ({
        ...r,
        track: { ...r.track, getSettings: () => ({}) },
      }));
    };
  }

  // ========== IFRAME CONTENTWINDOW FIX ==========

  const originalContentWindowGetter = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
  if (originalContentWindowGetter) {
    Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
      get: function() {
        try {
          return originalContentWindowGetter.get.call(this);
        } catch (e) {
          return null;
        }
      },
      configurable: true,
    });
  }

  // ========== toString() PROTECTION ==========

  const nativeToString = Function.prototype.toString;
  const proxyToString = new Proxy(nativeToString, {
    apply: function(target, thisArg, args) {
      if (thisArg === navigator.permissions.query) {
        return 'function query() { [native code] }';
      }
      return target.apply(thisArg, args);
    }
  });
  Function.prototype.toString = proxyToString;

  // ========== BATTERY API ==========

  if (navigator.getBattery) {
    navigator.getBattery = () => Promise.resolve({
      charging: true,
      chargingTime: 0,
      dischargingTime: Infinity,
      level: 1.0,
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => true,
    });
  }

  // ========== MEDIA DEVICES ==========

  if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
    navigator.mediaDevices.enumerateDevices = () => Promise.resolve([
      { kind: 'audioinput', deviceId: 'default', label: '', groupId: 'default' },
      { kind: 'audiooutput', deviceId: 'default', label: '', groupId: 'default' },
      { kind: 'videoinput', deviceId: 'default', label: '', groupId: 'default' },
    ]);
  }

  // ========== STORAGE QUOTA ==========

  if (navigator.storage && navigator.storage.estimate) {
    navigator.storage.estimate = () => Promise.resolve({
      quota: 299706064076,
      usage: 0,
    });
  }

  // ========== CLEANUP ==========

  // Remove stealth config from window
  delete window.__STEALTH_CONFIG__;

})();
"""


def pick_random_item(values: List[Any]) -> Any:
    """Pick a random item from a list."""
    return random.choice(values)


def generate_random_string(length: int = 8) -> str:
    """Generate a random alphanumeric string."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def get_available_os_browser_combos() -> List[Tuple[OSType, BrowserType]]:
    """Get all available OS/Browser combinations that have user agents."""
    return [combo for combo in USER_AGENTS.keys() if USER_AGENTS[combo]]


def generate_browser_profile(
    os_type: Optional[OSType] = None,
    browser_type: Optional[BrowserType] = None,
) -> BrowserProfile:
    """
    Generate a correlated browser profile for consistent fingerprinting.
    
    Args:
        os_type: Specific OS to use, or None for random
        browser_type: Specific browser to use, or None for random
        
    Returns:
        A BrowserProfile with all properties correlated
    """
    # Select OS and browser type
    available_combos = get_available_os_browser_combos()
    
    if os_type is None:
        os_type = random.choice([c[0] for c in available_combos])
    
    # Find compatible browsers for selected OS
    compatible_browsers = [c[1] for c in available_combos if c[0] == os_type]
    if browser_type is None:
        browser_type = random.choice(compatible_browsers)
    elif browser_type not in compatible_browsers:
        # Fallback to first compatible if specified one isn't available
        browser_type = compatible_browsers[0]
    
    # Select user agent
    ua_list = USER_AGENTS.get((os_type, browser_type), [])
    user_agent = random.choice(ua_list) if ua_list else USER_AGENTS[(OSType.WINDOWS, BrowserType.CHROME)][0]
    
    # Select viewport
    viewport = random.choice(VIEWPORT_PRESETS[os_type])
    
    # Calculate screen size (typically 1.25x viewport for Windows, 1x for Mac retina)
    screen_scale = 1.25 if os_type == OSType.WINDOWS else 1.0
    screen = {
        "width": int(viewport["width"] * screen_scale),
        "height": int(viewport["height"] * screen_scale),
    }
    
    # Select hardware specs
    specs = HARDWARE_SPECS[os_type]
    hardware_concurrency = random.choice(specs["cores"])
    device_memory = random.choice(specs["memory"])
    
    # Touch points (0 for desktop, >0 for mobile)
    max_touch_points = 0
    
    # Select locale
    locale = random.choice(LOCALES[os_type])
    
    # Select timezone (try to match locale)
    matching_timezones = [tz for tz in TIMEZONES if tz.get("locale", "").startswith(locale.split("-")[0])]
    if matching_timezones:
        timezone = random.choice(matching_timezones)["id"]
    else:
        timezone = random.choice(TIMEZONES)["id"]
    
    # Select geolocation (correlated with timezone)
    geo_options = GEO_LOCATIONS.get(timezone, GEO_LOCATIONS["America/New_York"])
    geolocation = random.choice(geo_options)
    
    return BrowserProfile(
        os_type=os_type,
        browser_type=browser_type,
        user_agent=user_agent,
        platform=PLATFORM_STRINGS[os_type],
        vendor=VENDOR_STRINGS[browser_type],
        viewport=viewport,
        screen=screen,
        hardware_concurrency=hardware_concurrency,
        device_memory=device_memory,
        max_touch_points=max_touch_points,
        locale=locale,
        timezone=timezone,
        geolocation=geolocation,
    )


def get_headers_for_profile(profile: BrowserProfile) -> Dict[str, str]:
    """Generate HTTP headers correlated with the browser profile."""
    headers = DEFAULT_HEADERS.copy()
    
    # Update language header
    headers["Accept-Language"] = f"{profile.locale},en;q=0.9"
    
    # Update Sec-Ch-Ua headers based on browser
    if profile.browser_type == BrowserType.CHROME:
        # Extract version from user agent
        version = "120.0.0.0"
        for part in profile.user_agent.split(" "):
            if "Chrome/" in part:
                version = part.split("/")[1].split(".")[0]
                break
        headers["Sec-Ch-Ua"] = f'"Not_A Brand";v="8", "Chromium";v="{version}", "Google Chrome";v="{version}"'
        headers["Sec-Ch-Ua-Platform"] = f'"{profile.platform}"'
    elif profile.browser_type == BrowserType.EDGE:
        version = "120.0.0.0"
        for part in profile.user_agent.split(" "):
            if "Edg/" in part:
                version = part.split("/")[1].split(".")[0]
                break
        headers["Sec-Ch-Ua"] = f'"Not_A Brand";v="8", "Chromium";v="{version}", "Microsoft Edge";v="{version}"'
        headers["Sec-Ch-Ua-Platform"] = f'"{profile.platform}"'
    elif profile.browser_type == BrowserType.FIREFOX:
        # Firefox doesn't send Sec-Ch-Ua headers
        headers.pop("Sec-Ch-Ua", None)
        headers.pop("Sec-Ch-Ua-Mobile", None)
        headers.pop("Sec-Ch-Ua-Platform", None)
    elif profile.browser_type == BrowserType.SAFARI:
        # Safari doesn't send Sec-Ch-Ua headers
        headers.pop("Sec-Ch-Ua", None)
        headers.pop("Sec-Ch-Ua-Mobile", None)
        headers.pop("Sec-Ch-Ua-Platform", None)
    
    return headers


def build_stealth_init_script(profile: BrowserProfile) -> str:
    """
    Build the initialization script with profile-specific configuration.
    
    Args:
        profile: BrowserProfile with configuration values
        
    Returns:
        JavaScript string with embedded config
    """
    config_js = f"""
window.__STEALTH_CONFIG__ = {{
  platform: '{profile.platform}',
  vendor: '{profile.vendor}',
  languages: {profile.locale.split('-')[0] == 'en' and "['en-US', 'en']" or f"['{profile.locale}', 'en']"},
  hardwareConcurrency: {profile.hardware_concurrency},
  deviceMemory: {profile.device_memory},
  maxTouchPoints: {profile.max_touch_points},
  viewportWidth: {profile.viewport['width']},
  viewportHeight: {profile.viewport['height']},
  screenScale: {profile.screen['width'] / profile.viewport['width']},
}};
"""
    return config_js + ANTI_BOT_INIT_SCRIPT


def build_anti_bot_context_options(
    profile: Optional[BrowserProfile] = None,
    use_stealth: bool = True,
) -> Dict[str, Any]:
    """
    Build Playwright context options with anti-bot configuration.
    
    Args:
        profile: Optional pre-generated profile, or None to generate random
        use_stealth: Whether to apply stealth techniques
        
    Returns:
        Dictionary of context options for browser.new_context()
    """
    if profile is None:
        profile = generate_browser_profile()
    
    options = {
        "viewport": profile.viewport,
        "user_agent": profile.user_agent,
        "locale": profile.locale,
        "timezone_id": profile.timezone,
        "permissions": ["geolocation", "notifications"],
        "geolocation": profile.geolocation,
        "color_scheme": profile.color_scheme,
        "is_mobile": profile.is_mobile,
        "has_touch": profile.max_touch_points > 0,
        "screen": profile.screen,
    }
    
    if use_stealth:
        options["extra_http_headers"] = get_headers_for_profile(profile)
        # Reduce automation flags
        options["ignore_https_errors"] = True
        
    return options


async def install_anti_bot_initial_scripts(
    context: BrowserContext,
    profile: Optional[BrowserProfile] = None,
) -> None:
    """
    Install anti-bot detection evasion scripts into a browser context.
    
    Args:
        context: Playwright BrowserContext
        profile: Optional profile to use, or None to extract from context
    """
    # Try to get profile from context options if not provided
    if profile is None:
        # Create a basic profile from context settings
        ua = await context.evaluate("() => navigator.userAgent")
        viewport = context.pages[0].viewport_size if context.pages else {"width": 1920, "height": 1080}
        profile = BrowserProfile(
            os_type=OSType.WINDOWS,
            browser_type=BrowserType.CHROME,
            user_agent=ua,
            platform="Win32",
            vendor="Google Inc.",
            viewport=viewport,
            screen={"width": viewport["width"], "height": viewport["height"]},
            hardware_concurrency=8,
            device_memory=8,
            max_touch_points=0,
            locale="en-US",
            timezone="America/New_York",
            geolocation={"latitude": 40.7128, "longitude": -74.0060},
        )
    
    # Build and install the script with profile config
    script = build_stealth_init_script(profile)
    await context.add_init_script(source=script)


async def create_stealth_context(
    browser,
    profile: Optional[BrowserProfile] = None,
    proxy: Optional[Dict[str, str]] = None,
) -> BrowserContext:
    """
    Create a fully configured stealth browser context.
    
    Args:
        browser: Playwright browser instance
        profile: Optional pre-generated profile
        proxy: Optional proxy configuration
        
    Returns:
        Configured BrowserContext with anti-detection measures
    """
    if profile is None:
        profile = generate_browser_profile()
    
    options = build_anti_bot_context_options(profile)
    
    if proxy:
        options["proxy"] = proxy
    
    context = await browser.new_context(**options)
    await install_anti_bot_initial_scripts(context, profile)
    
    return context


# Mobile-specific configurations
MOBILE_USER_AGENTS: List[Dict[str, Any]] = [
    {
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        "viewport": {"width": 390, "height": 844},
        "is_mobile": True,
        "has_touch": True,
        "platform": "iPhone",
        "max_touch_points": 5,
    },
    {
        "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "viewport": {"width": 412, "height": 915},
        "is_mobile": True,
        "has_touch": True,
        "platform": "Linux armv8l",
        "max_touch_points": 5,
    },
    {
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1",
        "viewport": {"width": 393, "height": 852},
        "is_mobile": True,
        "has_touch": True,
        "platform": "iPhone",
        "max_touch_points": 5,
    },
]


def generate_mobile_profile() -> BrowserProfile:
    """Generate a mobile browser profile."""
    mobile_config = random.choice(MOBILE_USER_AGENTS)
    
    return BrowserProfile(
        os_type=OSType.MACOS if "iPhone" in mobile_config["user_agent"] else OSType.LINUX,
        browser_type=BrowserType.SAFARI if "Safari/604" in mobile_config["user_agent"] else BrowserType.CHROME,
        user_agent=mobile_config["user_agent"],
        platform=mobile_config["platform"],
        vendor="Apple Computer, Inc." if "iPhone" in mobile_config["user_agent"] else "Google Inc.",
        viewport=mobile_config["viewport"],
        screen={"width": mobile_config["viewport"]["width"], "height": mobile_config["viewport"]["height"]},
        hardware_concurrency=6,
        device_memory=4,
        max_touch_points=mobile_config["max_touch_points"],
        locale="en-US",
        timezone="America/New_York",
        geolocation={"latitude": 40.7128, "longitude": -74.0060},
        color_scheme="light",
        is_mobile=True,
    )