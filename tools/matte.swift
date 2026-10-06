// Person cut-out masks for the Reels Editing Lab, using Apple's Vision framework (built into macOS).
// Usage: matte <in folder of JPEG frames> <out folder>
// Writes one grayscale PNG per frame (same name, .png): white = the person, black = background.
// Used for "behind me" moments: text or a picture placed behind the speaker, with them in front.
import CoreImage
import Foundation
import Vision

let inDir = URL(fileURLWithPath: CommandLine.arguments[1])
let outDir = URL(fileURLWithPath: CommandLine.arguments[2])
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
let files = (try FileManager.default.contentsOfDirectory(at: inDir, includingPropertiesForKeys: nil))
    .filter { $0.pathExtension.lowercased() == "jpg" }
    .sorted { $0.lastPathComponent < $1.lastPathComponent }

let ctx = CIContext()
let gray = CGColorSpace(name: CGColorSpace.linearGray)!
let request = VNGeneratePersonSegmentationRequest()
request.qualityLevel = .accurate
request.outputPixelFormat = kCVPixelFormatType_OneComponent8

for url in files {
    guard let src = CIImage(contentsOf: url) else { continue }
    let handler = VNImageRequestHandler(url: url, options: [:])
    do {
        try handler.perform([request])
        guard let buf = request.results?.first?.pixelBuffer else { continue }
        var mask = CIImage(cvPixelBuffer: buf)
        // scale the (smaller) mask up to the frame size
        let sx = src.extent.width / mask.extent.width, sy = src.extent.height / mask.extent.height
        mask = mask.transformed(by: CGAffineTransform(scaleX: sx, y: sy))
        let out = outDir.appendingPathComponent(url.deletingPathExtension().lastPathComponent + ".png")
        try ctx.writePNGRepresentation(of: mask, to: out, format: .L8, colorSpace: gray)
    } catch {
        FileHandle.standardError.write("\(url.lastPathComponent): \(error)\n".data(using: .utf8)!)
    }
}
