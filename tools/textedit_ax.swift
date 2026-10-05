// Focused editable text bridge loaded into Trinity's authorized Python process.
import AppKit
import ApplicationServices
import Foundation

private func focusedAppPID() -> pid_t? {
    guard AXIsProcessTrusted() else { return nil }
    var application: CFTypeRef?
    let system = AXUIElementCreateSystemWide()
    if AXUIElementCopyAttributeValue(system, kAXFocusedApplicationAttribute as CFString, &application) != .success {
        application = nil
        _ = AXUIElementCopyAttributeValue(system, kAXFocusedUIElementAttribute as CFString, &application)
    }
    guard let application else { return nil }
    var pid: pid_t = 0
    guard AXUIElementGetPid(application as! AXUIElement, &pid) == .success else { return nil }
    return pid
}

@_cdecl("trinity_focused_app_pid")
public func trinityFocusedAppPID() -> Int32 {
    return focusedAppPID() ?? 0
}

@_cdecl("trinity_ax_trusted")
public func trinityAXTrusted() -> Int32 {
    return AXIsProcessTrusted() ? 1 : 0
}

@_cdecl("trinity_ax_request")
public func trinityAXRequest() -> Int32 {
    let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
    return AXIsProcessTrustedWithOptions(options) ? 1 : 0
}

@_cdecl("trinity_focus_diagnostics")
public func trinityFocusDiagnostics() -> UnsafeMutablePointer<CChar>? {
    let system = AXUIElementCreateSystemWide()
    var app: CFTypeRef?
    let appError = AXUIElementCopyAttributeValue(system, kAXFocusedApplicationAttribute as CFString, &app)
    var element: CFTypeRef?
    let elementError = AXUIElementCopyAttributeValue(system, kAXFocusedUIElementAttribute as CFString, &element)
    var owner: pid_t = 0
    var role: CFTypeRef?
    if let element {
        _ = AXUIElementGetPid(element as! AXUIElement, &owner)
        _ = AXUIElementCopyAttributeValue(element as! AXUIElement, kAXRoleAttribute as CFString, &role)
    }
    var texteditError: Int32 = -1
    var texteditRole = ""
    if let textedit = NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.TextEdit").first {
        var texteditElement: CFTypeRef?
        texteditError = AXUIElementCopyAttributeValue(AXUIElementCreateApplication(textedit.processIdentifier),
            kAXFocusedUIElementAttribute as CFString, &texteditElement).rawValue
        if let texteditElement {
            var candidateRole: CFTypeRef?
            _ = AXUIElementCopyAttributeValue(texteditElement as! AXUIElement, kAXRoleAttribute as CFString, &candidateRole)
            texteditRole = candidateRole as? String ?? ""
        }
    }
    let payload: [String: Any] = ["trusted": AXIsProcessTrusted(),
        "workspace_pid": NSWorkspace.shared.frontmostApplication?.processIdentifier ?? 0,
        "focused_pid": focusedAppPID() ?? 0, "element_pid": owner,
        "app_error": appError.rawValue, "element_error": elementError.rawValue,
        "role": role as? String ?? "", "textedit_error": texteditError, "textedit_role": texteditRole]
    guard let data = try? JSONSerialization.data(withJSONObject: payload),
          let result = String(data: data, encoding: .utf8) else { return nil }
    return strdup(result)
}

private func focusedDocument() -> (AXUIElement, String, CFRange, pid_t)? {
    guard AXIsProcessTrusted(),
          let activePID = focusedAppPID() ?? NSWorkspace.shared.frontmostApplication?.processIdentifier else { return nil }
    guard activePID != getpid() else { return nil }
    let system = AXUIElementCreateApplication(activePID)
    _ = AXUIElementSetMessagingTimeout(system, 0.5)
    var focused: CFTypeRef?
    guard AXUIElementCopyAttributeValue(system, kAXFocusedUIElementAttribute as CFString, &focused) == .success,
          let focused else { return nil }
    let element = focused as! AXUIElement
    var owner: pid_t = 0
    guard AXUIElementGetPid(element, &owner) == .success,
          owner == activePID else { return nil }
    var role: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, kAXRoleAttribute as CFString, &role) == .success,
          [kAXTextAreaRole as String, kAXTextFieldRole as String].contains(role as? String ?? "") else { return nil }
    var subrole: CFTypeRef?
    _ = AXUIElementCopyAttributeValue(element, kAXSubroleAttribute as CFString, &subrole)
    guard (subrole as? String) != kAXSecureTextFieldSubrole as String else { return nil }
    var selectable: DarwinBoolean = false
    guard AXUIElementIsAttributeSettable(element, kAXSelectedTextRangeAttribute as CFString, &selectable) == .success,
          selectable.boolValue else { return nil }
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, kAXValueAttribute as CFString, &value) == .success,
          let text = value as? String else { return nil }
    guard (text as NSString).length <= 400_000 else { return nil }
    var selectionValue: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, kAXSelectedTextRangeAttribute as CFString, &selectionValue) == .success,
          let selectionValue else { return nil }
    var range = CFRange(location: 0, length: 0)
    guard AXValueGetValue(selectionValue as! AXValue, .cfRange, &range) else { return nil }
    return (element, text, range, owner)
}

@_cdecl("trinity_textedit_inspect")
public func trinityTexteditInspect() -> UnsafeMutablePointer<CChar>? {
    guard let (element, text, range, pid) = focusedDocument() else { return nil }
    let payload: [String: Any] = [
        "pid": pid,
        "text": text,
        "selection_start": range.location,
        "selection_length": range.length,
        "field_id": String(CFHash(element)),
    ]
    guard let data = try? JSONSerialization.data(withJSONObject: payload),
          let result = String(data: data, encoding: .utf8) else { return nil }
    return strdup(result)
}

@_cdecl("trinity_textedit_select")
public func trinityTexteditSelect(_ start: Int32, _ length: Int32) -> Int32 {
    guard let (element, text, _, _) = focusedDocument() else { return 1 }
    let count = (text as NSString).length
    guard start >= 0, length >= 0, Int(start) + Int(length) <= count else { return 2 }
    var range = CFRange(location: Int(start), length: Int(length))
    guard let value = AXValueCreate(.cfRange, &range),
          AXUIElementSetAttributeValue(element, kAXSelectedTextRangeAttribute as CFString, value) == .success else {
        return 3
    }
    return 0
}

@_cdecl("trinity_textedit_free")
public func trinityTexteditFree(_ value: UnsafeMutablePointer<CChar>?) {
    free(value)
}
