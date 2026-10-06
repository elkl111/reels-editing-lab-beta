// Face finder for the Reels Editing Lab, using Apple's Vision framework (built into macOS).
// Usage: faces <folder of frame JPEGs>  → prints JSON lines: {"file", "box":[x,y,w,h], "quality", "eyes"}
// box is normalised 0–1 with a TOP-left origin. quality = Apple's face capture quality
// (sharpness, eyes, expression; the score Photos uses to choose good shots).
// eyes = how open the eyes are (eye height / eye width, averaged; ~0.25+ is open).
import Foundation
import Vision

func eyeOpen(_ region: VNFaceLandmarkRegion2D?) -> Double? {
    guard let r = region, r.pointCount > 2 else { return nil }
    let pts = r.normalizedPoints
    let xs = pts.map { Double($0.x) }, ys = pts.map { Double($0.y) }
    let w = (xs.max()! - xs.min()!), h = (ys.max()! - ys.min()!)
    return w > 0 ? h / w : nil
}

let dir = URL(fileURLWithPath: CommandLine.arguments[1])
let files = (try FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil))
    .filter { $0.pathExtension.lowercased() == "jpg" }
    .sorted { $0.lastPathComponent < $1.lastPathComponent }

for url in files {
    let landmarks = VNDetectFaceLandmarksRequest()
    let quality = VNDetectFaceCaptureQualityRequest()
    let handler = VNImageRequestHandler(url: url, options: [:])
    var out: [String: Any] = ["file": url.lastPathComponent]
    do {
        try handler.perform([landmarks, quality])
        // the biggest face is the speaker
        if let face = (landmarks.results ?? []).max(by: { $0.boundingBox.width < $1.boundingBox.width }) {
            let b = face.boundingBox
            out["box"] = [Double(b.minX), Double(1 - b.maxY), Double(b.width), Double(b.height)]
            let l = eyeOpen(face.landmarks?.leftEye), r = eyeOpen(face.landmarks?.rightEye)
            let eyes = [l, r].compactMap { $0 }
            if !eyes.isEmpty { out["eyes"] = eyes.reduce(0, +) / Double(eyes.count) }
            if let q = (quality.results ?? []).max(by: { $0.boundingBox.width < $1.boundingBox.width }),
               let s = q.faceCaptureQuality {
                out["quality"] = Double(s)
            }
        }
    } catch {
        out["error"] = "\(error)"
    }
    let data = try JSONSerialization.data(withJSONObject: out)
    print(String(data: data, encoding: .utf8)!)
}
