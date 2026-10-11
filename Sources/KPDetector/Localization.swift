import Foundation

/// Texte localisé (clé = texte anglais ; traductions dans Resources/<lang>.lproj).
func L(_ key: String, _ args: CVarArg...) -> String {
    let format = NSLocalizedString(key, comment: "")
    return args.isEmpty ? format : String(format: format, arguments: args)
}
