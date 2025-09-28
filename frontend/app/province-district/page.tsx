'use client';
import React, { useEffect, useState, Fragment } from 'react';
import { Card, Table, Row, Col, Breadcrumb, Spin, Select, Space, Typography } from 'antd';
import { DatabaseOutlined} from '@ant-design/icons';
import { API_BASE, apiForm } from '@/lib/api';
import type { TableProps } from 'antd';

type FilterOption = {
  province_id: { value: string; label: React.ReactNode } | 'all';
  district_id: { value: string; label: React.ReactNode } | 'all';
};

type DataSource = {
	page: number;
	page_size: number;
	total: number;
	all_page: number;
	items: any[]
};

type DataProvince = {
	province_id: number;
	province_name: string;
	province_name_en: string;
};


type DataDistrict = {
	district_id: number;
	district_name: string;
	district_name_en: string;
};

export default function ProvinceDistrict() {
	const [isLoading, setIsLoading] = useState(false);
	const [orderField, setOrderField] = useState('province_id');
	const [orderType, setOrderType] = useState('asc');
	const [dataSource, setDataSource] = useState<DataSource>({
		page: 1,
		page_size: 10,
		total: 0,
		all_page: 0,
		items: [],
	});
	const [dataProvince, setDataProvince] = useState<DataProvince[]>([]);
	const [dataDistrict, setDataDistrict] = useState<DataDistrict[]>([]);
	const [filterOption, setFilterOption] = useState<FilterOption>({
		province_id : 'all',
		district_id : 'all',
	});
	const [page, setPage] = useState(1);
  	const [pageSize, setPageSize] = useState(10);



	async function refresh(p=page, ps=pageSize, order_by=orderField, order_type=orderType, province_id=filterOption.province_id, district_id=filterOption.district_id, init: RequestInit = {}) {
		try {
			setIsLoading(true);
			const res = await fetch(`${API_BASE}/list_province_district?page=${p}&page_size=${ps}&order_by=${order_by}&order_type=${order_type}&province_id=${province_id}&district_id=${district_id}`, { 
				cache: "no-store",
				credentials: 'include',
				headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
				...init,
			});

			setDataSource(await res.json());
		} catch (e: any) {
			setIsLoading(false);
		} finally {
			setIsLoading(false);
		}
	}

	const onChangeTable: TableProps<any>['onChange'] = (pagination, filters, sorter:any, extra) => {
		if(extra.action == 'sort') {
			if(typeof sorter.order !== 'undefined') {
				setPage(1);
				setOrderField(sorter.field)
				setOrderType((sorter.order == 'descend' ? 'desc' : 'asc'))
			} else {
				setPage(1);
				setOrderField('province_id')
				setOrderType('asc')
			}
		}

	};

	useEffect(() => {
		refresh();
	}, [page, pageSize, orderField, orderType, filterOption])

	useEffect(() => {
		async function fetchDistrict(province_id = filterOption.province_id, init: RequestInit = {}) {
			try {
				const res = await fetch(`${API_BASE}/list_district?province_id=${province_id}`, { 
					cache: "no-store",
					credentials: 'include',
					headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
					...init,
				});

				const dataOption = await res.json()
				if(dataOption.total > 0) {
					setDataDistrict([{
						value: "all",
						label: "ทั้งหมด (All)",
					}, ...dataOption.items.map((ele:any) => {
						return {
							value: ele.district_id,
							label: ele.district_name + ' (' + ele.district_name_en+ ')',
						}
					})]);
				} else {
					setDataDistrict([]);
				}
			} catch (e: any) {
				setDataDistrict([]);
			}
		}

		fetchDistrict();
	}, [filterOption.province_id])

	useEffect(() => {
		async function fetchProvince(init: RequestInit = {}) {
			try {
				const res = await fetch(`${API_BASE}/list_province`, { 
					cache: "no-store",
					credentials: 'include',
					headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
					...init,
				});

				const dataOption = await res.json()
				

				if(dataOption.total > 0) {
					setDataProvince([{
						value: "all",
						label: "ทั้งหมด (All)",
					}, ...dataOption.items.map((ele:any) => {
						return {
							value: ele.province_id,
							label: ele.province_name + ' (' + ele.province_name_en+ ')',
						}
					})]);
				} else {
					setDataProvince([]);
				}
			} catch (e: any) {
				setDataProvince([]);
			}
		}

		fetchProvince();
	}, [])

	const handleChangeProvince = (value:any) => {
		if(value != 'all') {
			setFilterOption({
				province_id : value,
				district_id : 'all',
			})
		} else {
			setFilterOption({
				province_id : value,
				district_id : filterOption.district_id,
			})
		}
		setPage(1);
	}

	const handleChangeDistrict = (value:any) => {
		setFilterOption({
			province_id : filterOption.province_id,
			district_id : value,
		})
		setPage(1);
	}

	
	return (
		<Fragment>
			<Breadcrumb className="breadcrumb-design" separator={`>`}
				items={[{ title: 'Home', path: '/', }, { title: 'Province / District' }]}
			/>
			<div className="block-content">
				<Row gutter={[16, 16]}>
					<Col span={24}>
						<Spin spinning={isLoading} size={`large`}>
							<Card title={<span><DatabaseOutlined /> Province / District</span>}>
								
								<Row gutter={[24, 24]}>
									<Col span={24} className="text-right">
										<Space size={`large`}>

											<Space>
												<Typography.Text>จังหวัด (Province) : </Typography.Text>
												<Select
													showSearch
													filterOption={(input:any, option:any) => (option?.label?.toLowerCase() ?? '').includes(input?.toLowerCase())}
													// defaultValue={{ value: 'all', label: 'ทั้งหมด (All)' }}
													value={filterOption.province_id}
													options={dataProvince}
													style={{ width: 250, textAlign: `left` }}
													onChange={handleChangeProvince}
												/>
											</Space>

											<Space>
												<Typography.Text>อำเภอ (District) : </Typography.Text>
												<Select
													showSearch
													filterOption={(input:any, option:any) => (option?.label?.toLowerCase() ?? '').includes(input?.toLowerCase())}
													// defaultValue={{ value: 'all', label: 'ทั้งหมด (All)' }}
													value={filterOption.district_id}
													options={dataDistrict}
													style={{ width: 350, textAlign: `left` }}
													onChange={handleChangeDistrict}
												/>
											</Space>
											
										</Space>
									</Col>
									<Col span={24}>
										<Table
											rowKey="id"
											dataSource={dataSource.items}
											columns={[
												{ 
													title: 'No.', 
													align:'center', 
													width: 50, 
													render: (value:string, record:any, index:number) => {
														return (((dataSource.page - 1) * dataSource.page_size) + (index + 1)).toLocaleString();
													}
												},
												{ 
													title: 'จังหวัด (Province)', 
													dataIndex: 'province_name',
													sortDirections: ['ascend', 'descend'],
													width: 400,
													sorter: true,
													render: (value:string, record:any) => {
														return record.province_name + ' (' + record.province_name_en + ')'
													} 
												},
												{ 
													title: 'อำเภอ (District)', 
													dataIndex: 'district_name',
													sortDirections: ['ascend', 'descend'],
													sorter: true,
													width: 400,
													render: (value:string, record:any) => {
														return record.district_name + ' (' + record.district_name_en + ')'
													}
												},
											]}
											pagination={{
												simple:true,
												current: dataSource?.page ?? 1,
												pageSize: dataSource?.page_size ?? 10,
												total: dataSource?.total ?? 0,
												showSizeChanger: true,
												showTotal: (total:number) => {
													return `จำนวนทั้งหมด (Total) ${total.toLocaleString()} รายการ (Items)`
												},
												onChange: (p:number, ps:number) => {
													setPage(p);
													setPageSize(ps);
												},
												locale: {items_per_page: "หน้า (Page)"}
											}}
											onChange={onChangeTable}
										/>
									</Col>
								</Row>
									
							</Card>
						</Spin>
					</Col>
				</Row>
			</div>
		</Fragment>
	);
}