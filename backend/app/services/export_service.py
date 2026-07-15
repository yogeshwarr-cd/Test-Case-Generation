import csv,io,json
class ExportService:
    @staticmethod
    def prepare(rows,fmt):
        data=[{c.name:getattr(r,c.name) for c in r.__table__.columns} for r in rows]
        if fmt=="json": return json.dumps(data,default=str),"application/json"
        output=io.StringIO()
        if data:
            writer=csv.DictWriter(output,fieldnames=data[0]);writer.writeheader();writer.writerows(data)
        return output.getvalue(),"text/csv"
